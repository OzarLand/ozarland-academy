---
title: Fact sheet C
description: "Fact sheet for Glance, Placement, Cinder, Horizon and Heat in 2024.1: per-role flow, bootstrap on reconfigure, dependencies and restart impact."
tags: [glance, placement, cinder, horizon, heat, reconfigure, one-shot]
---

# Fact sheet C

All paths are relative to the repo root (`$SRC`). Every claim comes from reading source code only: kolla-ansible at the
tag `2024.1-eom`, the kolla images repo at the tag `2024.1-eom`, and, for Ansible semantics, the Ansible source (cited
as ansible-core 2.16.20 `lib/ansible/...:N`). Modules run inside the kolla-toolbox image come from that image's
`ansible-core==2.16.*` plus Ansible collections (kolla `docker/kolla-toolbox/Dockerfile.j2:76`,
`docker/kolla-toolbox/requirements.yml:2-13`); the collection sources installed in that image are not among the studied
trees.
- **FACT** (the default, not written out): shown by the cited source lines.
- **NOT AVAILABLE**: the sources do not establish it, for example upstream OpenStack runtime behaviour, durations, or
  what a restart does to work in progress.

Behaviour inside the images (what `KOLLA_BOOTSTRAP`, `KOLLA_UPGRADE`, `KOLLA_OSM`, `GLANCE_DB_EXPAND` and similar
variables actually run) is defined in the separate `kolla` images repo, whose `2024.1-eom` tag was read (see
[Kolla images](../../concepts/kolla-images.md)). A statement that cites a kolla path, written as kolla `docker/...` (for
example kolla `docker/glance/glance-api/extend_start.sh` or kolla `docker/base/set_configs.py`), is read from that
source like any other code claim. Image-side behaviour without such a citation is NOT AVAILABLE.

> [!NOTE]
> **Key answers**
>
> - **Reconfigure runs the bootstrap (schema sync) container** in all five roles (for Horizon only with its DB backend),
>   exactly as deploy does; this still holds in 2024.1 ([§0](#0-cross-cutting-facts-apply-to-all-five-roles),
>   [§6](#6-summary-matrix-what-reconfigure-does-per-role)).
> - **Changed in 2024.1, External Ceph layout:** Glance and Cinder now copy one `<cluster>.conf` and
>   `<cluster>.<keyring>` per Ceph backend into a `ceph/` sub-directory, and `config.json` copies that directory to
>   `/etc/ceph`; the first 2024.1 run therefore changes the files of `glance-api`, `cinder-volume` and `cinder-backup`
>   ([§1.4](#14-config-files-ansiblerolesglancetasksconfigyml),
>   [§3.4](#34-config-files-ansiblerolescindertasksconfigyml)).
> - **Changed in 2024.1, Horizon settings files:** kolla-ansible no longer writes `local_settings` and
>   `custom_local_settings`; it writes `_9998-kolla-settings.py` and `_9999-custom-settings.py` into `local_settings.d`,
>   and an override kept under the old names is no longer looked up
>   ([§4.4](#44-config-files-ansibleroleshorizontasksconfigyml)).
> - **New in 2024.1:** an S3 backend for Glance and for Cinder backup, a `hostnqn` file for `cinder-volume`, and
>   RabbitMQ quorum queues on by default in the Glance, Cinder and Heat configs
>   ([§1.7](#17-dependencies-from-templatesglance-apiconfj2), [§3.4](#34-config-files-ansiblerolescindertasksconfigyml),
>   [F17](../findings.md#f17)).
> - **Still holds:** the Glance file backend runs a single `glance-api` with no HA, Cinder's upgrade restarts every
>   Cinder container twice, and `bootstrap_heat` never updates the `heat_domain_admin` password
>   ([§1.8](#18-operational-notes), [§3.8](#38-operational-notes), [§5.6](#56-bootstrap)).

---

## 0. Cross-cutting facts (apply to all five roles)

| Topic | Fact | Evidence |
|---|---|---|
| Task dispatch | Every role's `tasks/main.yml` is `- include_tasks: "{{ kolla_action }}.yml"`. | e.g. `ansible/roles/glance/tasks/main.yml:2` (identical in placement/cinder/horizon/heat) |
| `reconfigure` | `reconfigure.yml` is just `- import_tasks: deploy.yml` in **all five** roles, so reconfigure performs keystone registration, DB create/grant and **the bootstrap (db sync) container**, exactly as deploy does. Still holds in 2024.1. | `ansible/roles/{glance,placement,cinder,horizon,heat}/tasks/reconfigure.yml:2` |
| `common` | In 2024.1 none of the five roles has a `meta/` directory (each holds only `defaults`, `handlers`, `tasks`, `templates`, `vars`), so there is no role dependency on `common`. `common` is its own play, tagged `common`, on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` groups. | `ansible/roles/{glance,placement,cinder,horizon,heat}/` (no `meta/`); `ansible/site.yml:88-103` |
| Serial | Every play uses `serial: '{{ kolla_serial|default("0") }}'`. The CLI passes `kolla_serial=${ANSIBLE_SERIAL}` (default `0`) only for `upgrade` and `reconfigure`. | `ansible/site.yml:549,584,598,731,747`; `tools/kolla-ansible:296,522,531` |
| `max_fail_percentage` | New in 2024.1: each of the five plays sets `max_fail_percentage: {{ <svc>_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}`. With the default 100 it never stops a play early: the ratio counts only the failures of the current batch (see [Controlled batches](../../operations/controlled-batches.md)). | `ansible/site.yml:550-553,585-588,599-602,732-735,748-751`; ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:184-190`, `lib/ansible/executor/task_queue_manager.py:330-338` |
| run_once + serial | Bootstrap, DB and keystone tasks are `run_once: True`. When `kolla_serial` > 0, Ansible runs the whole play once per batch and sends a `run_once` task only to the first host of the current batch, so `run_once` tasks run **once per batch**. So db sync and keystone registration repeat for each batch. This matters for glance rolling upgrade ([§1.8](#18-operational-notes)). | e.g. `ansible/roles/cinder/tasks/bootstrap_service.yml:19-20`; ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:181-190`, `lib/ansible/plugins/strategy/linear.py:181,208-209` |
| Bootstrap container | `kolla_container action=start_container, detach: False, restart_policy: oneshot` (the module was `kolla_docker` in 2023.1). With Docker, a one-shot container gets no systemd unit and is started directly; the module waits for exit, then stops and removes it (`remove_on_exit` defaults to True), before it reports a non-zero exit. Nothing guards it with "already bootstrapped", so it **runs on every deploy/reconfigure**. | `ansible/library/kolla_container.py:295,314`; `ansible/module_utils/kolla_docker_worker.py:338-339,379-413`; e.g. `ansible/roles/glance/tasks/bootstrap_service.yml:19-37` |
| Restart semantics | Handlers use `recreate_or_restart_container` and pass `common_options: docker_common_options`, which carries `graceful_timeout: docker_graceful_timeout` (**60 s**) and, new in 2024.1, `container_engine: kolla_container_engine`. Long-running containers run under a systemd unit `kolla-<name>-container.service` whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`; restarts and stops go through systemd `RestartUnit`/`StopUnit`. With Docker, SIGTERM is sent, then SIGKILL if the container is still running after 60 s. No role here overrides it. The 10 s value is only the module default when no `graceful_timeout` is passed. The unit template text changed in 2024.1, so the first 2024.1 check of a container whose unit 2023.1 wrote reports drift ([F16](../findings.md#f16)). | `ansible/group_vars/all.yml:139,142-153`; `ansible/module_utils/kolla_systemd_worker.py:20-39,106-125`; `ansible/module_utils/kolla_docker_worker.py:341-363,415-459`; `ansible/library/kolla_container.py:370`; [R24](../../risk/risk-register.md#r24) |
| Handler skip | All handlers have `when: kolla_action != "config"`, so `genconfig` never restarts anything. | e.g. `ansible/roles/cinder/handlers/main.yml:15-16` |
| Network | With Docker, all containers run with `network_mode: host`, so the container hostname is the node hostname (this matters for cinder `host`). | `ansible/module_utils/kolla_docker_worker.py:279` |
| Empty volume strings | Volume lists contain `''` entries (timezone, dev-mode, and in 2024.1 the `/dev/shm` entry of the queue manager). `generate_volumes` skips empty entries, so the places that pass lists without `reject('equalto','')` (placement/cinder upgrade OSM, horizon) are harmless. | `ansible/module_utils/kolla_container_worker.py:412-414` |
| Shared endpoints | `database_address: "{{ kolla_internal_fqdn }}"` (DB is reached through the VIP). `rpc_transport_url` / `notify_transport_url` enumerate **every** host in the rabbit groups. | `ansible/group_vars/all.yml:83,248,258` |
| memcached | Every service template (glance, placement, cinder, heat, horizon) enumerates **all** `groups['memcached']` hosts. Adding or removing a memcached or rabbitmq node therefore changes the config of all five services, and they restart on the next deploy/reconfigure. | e.g. `ansible/roles/heat/templates/heat.conf.j2:46,52` |
| RabbitMQ quorum queues | New default in 2024.1: `om_enable_rabbitmq_quorum_queues: true`, rendered as `rabbit_quorum_queue = true` in the glance, cinder and heat configs. A cloud that kept the 2023.1 default gets a changed config, so a restart, on its first 2024.1 deploy/reconfigure ([F17](../findings.md#f17)). Placement and Horizon have no `[oslo_messaging_rabbit]` section. | `ansible/group_vars/all.yml:268`; `ansible/roles/glance/templates/glance-api.conf.j2:139-148`; `ansible/roles/cinder/templates/cinder.conf.j2:90-99`; `ansible/roles/heat/templates/heat.conf.j2:74-98` |
| Workers | `openstack_service_workers: "{{ [ansible_facts.processor_vcpus, 5] | min }}"`. The value is per host. | `ansible/group_vars/all.yml:699` |
| Sanity checks | 2024.1 has no sanity checks: `kolla_enable_sanity_*` is defined nowhere under `ansible/`, glance and cinder have no `check.yml`, and the `check.yml` of placement, horizon and heat is empty. The CLI has no `check` action. | `grep -rn sanity ansible/` → nothing; `ansible/roles/{placement,horizon,heat}/tasks/check.yml:1`; `tools/kolla-ansible:438-598` |
| HAProxy | Each role's `loadbalancer.yml` is applied from the **loadbalancer play** (`site.yml:105-327`, tags `haproxy`, `keepalived`, `loadbalancer`), whose task block only runs when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']`. | `ansible/site.yml:105-121,325-327` |
| TLS backend certs | `service-cert-copy` copies `<project>-cert.pem`/`-key.pem` into a service's config dir only when one of its haproxy entries is enabled and one has `tls_backend` true, and `kolla_externally_managed_cert` is false. It notifies the container restart. | `ansible/roles/service-cert-copy/tasks/main.yml:14-56` |
| Service-to-host mapping | `host_in_groups` (used only by glance) takes precedence over `group` in the filter `select_services_enabled_and_mapped_to_host`. That filter drives pull/stop/cert-copy. | `kolla_ansible/filters.py:60-83,99-109` |
| Ansible forks | No `ansible.cfg` ships in the repo, so "all hosts restart together" really means up to `forks` hosts at once (Ansible default 5): Ansible starts at most `min(forks, batch size)` workers and queues each host's task on a free one. The `forks` value in use depends on the operator's config (`ansible.cfg`, `ANSIBLE_FORKS` or `kolla-ansible --forks`) and is NOT AVAILABLE here. | `find . -name ansible.cfg` → none; `tools/kolla-ansible:381-382`; ansible-core 2.16.20 `lib/ansible/config/base.yml:639-646`, `lib/ansible/executor/task_queue_manager.py:320-321`, `lib/ansible/plugins/strategy/__init__.py:352,387-429` |
| Container engine | New in 2024.1: the module dispatches to a Podman worker when `kolla_container_engine` is not `docker` (default `docker`). Cinder-volume and cinder-backup then mount `/run` without `:shared` plus the `run_default_volumes_podman` sub-mounts. This sheet reads the Docker path; Podman behaviour on a host is NOT AVAILABLE. | `ansible/group_vars/all.yml:92,153,165-172`; `ansible/roles/cinder/defaults/main.yml:43,52,175,193` |

### site.yml order (relevant slice)

`loadbalancer` play (105) → … → **glance** (544) → ironic (558) → **cinder** (576) → **placement** (593) →
`import_playbook: nova.yml` (609) → … → **heat** (724) → **horizon** (740). Placement is therefore (re)deployed before
nova, and glance before cinder. Still holds in 2024.1 (`ansible/site.yml:105,544,558,576,593,609,724,740`).

---

## 1. GLANCE

### 1.1 Play

```yaml
# ansible/site.yml:544-556
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
- `enable_glance: "{{ enable_openstack_core | bool }}"` (`ansible/group_vars/all.yml:722`).

### 1.2 `glance_services` (`ansible/roles/glance/defaults/main.yml:2-64`)

In 2024.1 the dict is at `ansible/roles/glance/defaults/main.yml:2-68`.

| key | container | group / mapping | enabled | flags |
|---|---|---|---|---|
| glance-api | `glance_api` | `group: glance-api`, **`host_in_groups: inventory_hostname in glance_api_hosts`** (:6) | `true` | `privileged: enable_cinder and (enable_cinder_backend_iscsi or cinder_backend_ceph)` (:10); `environment: glance_api_container_proxy` = `container_proxy` (:9, :215). This is the only service in scope that receives http(s)_proxy. Volumes (:193-203): `glance_file_datadir_volume:/var/lib/glance/` (default named volume `glance`), `/dev/shm` when `om_enable_queue_manager` (new, :200), and **`iscsi_info:/etc/iscsi` plus `/dev:/dev` when cinder iSCSI is enabled** (:202-203). |
| glance-tls-proxy | `glance_tls_proxy` | same `host_in_groups` (:39) | `glance_enable_tls_backend` (= `kolla_enable_tls_backend`, `all.yml:1013`) | HAProxy image (`.../haproxy`, :160-162). It listens on `api_interface_address:9292` with TLS and forwards to glance-api on `127.0.0.1`, port 9292 (`templates/glance-tls-proxy.cfg.j2:40-45`; glance-api `bind_host = 127.0.0.1` when TLS, `templates/glance-api.conf.j2:9-13`). Changed in 2024.1: the proxy uses `nbthread {{ glance_tls_proxy_threads }}` instead of `nbproc`, so a 2023.1 override of `glance_tls_proxy_processes` is no longer read (`defaults/main.yml:286-287`; `templates/glance-tls-proxy.cfg.j2:9-12`). |

**Critical mapping rule:**
```yaml
# ansible/group_vars/all.yml:1001,1006-1007,1011
glance_backend_file: "{{ not (glance_backend_ceph | bool or glance_backend_s3 | bool or glance_backend_swift | bool or glance_backend_vmware | bool) }}"
glance_backend_swift: "{{ enable_swift | bool }}"
glance_file_datadir_volume: "glance"
glance_api_hosts: "{{ [groups['glance-api'] | first] if glance_backend_file | bool and glance_file_datadir_volume == 'glance' else groups['glance-api'] }}"
```
With the default file backend on a local named volume, glance-api runs **only on the first host of `glance-api`**.
HAProxy members are built from `glance_api_hosts` too (`defaults/main.yml:86-87`), so glance has **no HA**. A glance-api
restart is a full Image API outage. The docs confirm this: "By default when using ``file`` backend only one
``glance-api`` container can be running" (`doc/source/reference/shared-services/glance-guide.rst:25-27`). Changed in
2024.1: `glance_backend_s3` (default `"no"`, `all.yml:1004`) is a new way to leave the file backend.

HAProxy: client and server timeouts are **6h** (`defaults/main.yml:139-140`). In TLS mode the HAProxy members are the
`custom_member_list` `haproxy_tls_members`, which always carries `ssl verify required ca-file ...`
(`defaults/main.yml:55,67,87`), and **ignore `kolla_verify_tls_backend`**: the template prints a custom member list as
is (`haproxy-config/templates/haproxy_single_service_split.cfg.j2:85-88`). Other services honour it in
`haproxy-config/templates/haproxy_single_service_split.cfg.j2:91-97`.

### 1.3 Task flow per action

| action | flow |
|---|---|
| deploy / reconfigure | `deploy.yml`: `register.yml` → `config.yml` → `check-containers.yml` → (`clone.yml` if dev) → `bootstrap.yml` → `meta: flush_handlers` (`tasks/deploy.yml:1-15`; `reconfigure.yml:2`). There is no `check.yml` step. |
| upgrade | `upgrade.yml:1-6`: `rolling_upgrade.yml` if `glance_enable_rolling_upgrade` (default `no`, `all.yml:1008`), else `legacy_upgrade.yml`. **No `register.yml`** in either path, so endpoints are not refreshed on upgrade. |
| legacy upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync, new image) → flush (`tasks/legacy_upgrade.yml:1-9`). It does **not** stop glance-api first. The docs claim "This upgrade method will stop APIs during database schema migrations" (`glance-guide.rst:143`), but the code does not do that: the old glance-api keeps serving while the new-image bootstrap migrates the schema. |
| rolling upgrade | see [§1.8](#18-operational-notes) |
| deploy-containers | `check-containers.yml` only, then handlers (`tasks/deploy-containers.yml:2`) |
| pull | `service-images-pull`. Only hosts where `host_in_groups` is true pull (`roles/service-images-pull/tasks/main.yml:14`). |
| stop | `service-stop` with `glance_services` (`tasks/stop.yml:2-6`) |
| precheck | `service-precheck` (groups exist) plus a free-port check on 9292 when glance_api is not running (`tasks/precheck.yml:1-26`). New in 2024.1: when `glance_backend_s3`, an assert that the four `glance_backend_s3_*` variables are defined (`tasks/precheck.yml:28-38`). |
| check | Not available in 2024.1: the role has no `check.yml`, and the CLI has no `check` action ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). |
| config | `config.yml` only. Handlers are notified but skipped. |

### 1.4 Config files (`ansible/roles/glance/tasks/config.yml`)

| dest (under `/etc/kolla/`) | source / merge order | when | notifies |
|---|---|---|---|
| `glance-api/` and `glance-tls-proxy/` dirs | `file` | enabled and mapped (:2-13) | – |
| `glance-api/ceph/` dir | `file`, mode 0770 (`external_ceph.yml:2-14`) | `glance_backend_ceph` (`config.yml:15-17`) | – |
| `glance-api/ceph/<cluster>.conf` | **changed in 2024.1:** `merge_configs` of `{{node_custom_config}}/glance/<cluster>.conf` + `glance/glance-api/<cluster>.conf`, once per entry of `glance_ceph_backends` (default one entry, cluster `ceph`, `defaults/main.yml:240-244`). In 2023.1 it was a single `template` of `glance/ceph.conf` to `glance-api/ceph.conf`. | `glance_backend_ceph` (`external_ceph.yml:16-27`) | Restart glance-api |
| `glance-api/ceph/<cluster>.<ceph_glance_keyring>` | `template {{node_custom_config}}/glance/<cluster>.<ceph_glance_keyring>`; the keyring default is now `client.glance.keyring` (`all.yml:1184`), so the default operator file name stays `ceph.client.glance.keyring` | ceph (`external_ceph.yml:29-38`) | Restart glance-api |
| policy file | first found of `supported_policy_format_list` in `{{node_custom_config}}/glance/` (:19-36, :156-169) | if found | Restart glance-api |
| CA/TLS certs | `copy-certs.yml` → service-cert-copy (:38-40) | `kolla_copy_ca_into_containers or glance_enable_tls_backend` | Restart `<svc>` |
| `glance-tls-proxy/glance-cert-and-key.pem` | `assemble` of `glance-(cert|key).pem` (:42-54) | TLS proxy enabled | **no notify** (the cert copy notifies instead) |
| `<svc>/config.json` | `glance-api.json.j2`, `glance-tls-proxy.json.j2` (:56-67) | – | Restart `<svc>` |
| `glance-api/glance-api.conf` | merge: `templates/glance-api.conf.j2` → `global.conf` → `glance.conf` → `glance/glance-api.conf` → `glance/<host>/glance-api.conf` (:69-86) | – | Restart glance-api |
| `glance-api/glance-cache.conf` | merge: template → `glance-cache.conf` → `glance/glance-cache.conf` → `glance/<host>/glance-cache.conf` (:88-105). Note that **no `global.conf`** is in this merge. | `enable_glance_image_cache` | Restart glance-api |
| `glance-api/glance-swift.conf` | merge: template → `glance-swift.conf` → `glance/glance-swift.conf` → `glance/<host>/...` (:107-124) | `glance_backend_swift` | Restart glance-api |
| `glance-api/glance-image-import.conf` | `copy {{node_custom_config}}/glance/glance-image-import.conf` (:126-139) | `glance_enable_interoperable_image_import` (default `no`, `all.yml:1010`) | Restart glance-api |
| `glance-api/property-protections-rules.conf` | `copy {{node_custom_config}}/glance/property-protections-rules.conf` (:141-154) | `glance_enable_property_protection` (default `no`, `all.yml:1009`) | Restart glance-api |
| `glance-tls-proxy/glance-tls-proxy.cfg` | first_found: `glance/<host>/glance-tls-proxy.cfg` → `glance/glance-tls-proxy.cfg` → role template (:171-187) | TLS proxy | Restart glance-tls-proxy |

Changed in 2024.1: with Ceph, `glance-api.json.j2` copies the whole `ceph` directory to `/etc/ceph`
(`templates/glance-api.json.j2:15-21`) instead of two separate files. Because the files sit at a new path and the
`config.json` content changes, the first 2024.1 deploy/reconfigure with `glance_backend_ceph` notifies the glance-api
restart.

`glance-api.json.j2:47-52` has
`"permissions": [{"path": "/var/lib/glance", "owner": "glance:glance", "recurse": true}]`. `/var/lib/glance` is the
`glance_file_datadir_volume` mount (`defaults/main.yml:197`), which with the file backend is the **entire image store**
(`filesystem_store_datadir = /var/lib/glance/images/`, `templates/glance-api.conf.j2:65`). kolla_set_configs walks it
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
| `mysql_user glance` with password and `ALL` on `glance.*` | `bootstrap.yml:18-36` | yes. The task runs `mysql_user` through `kolla_toolbox`, which runs `ansible localhost -m mysql_user` in the toolbox container (`ansible/library/kolla_toolbox.py:113-116`), whose image installs `ansible-core==2.16.*` (kolla `docker/kolla-toolbox/Dockerfile.j2:76`); ansible-core redirects `mysql_user` to `community.mysql.mysql_user` (ansible-core 2.16.20 `lib/ansible/config/ansible_builtin_runtime.yml:1401-1402`), installed in the image from `community.mysql <3` (kolla `docker/kolla-toolbox/requirements.yml:6-7`). That collection's source is not among the studied trees, so whether each run resets the stored password when it differs is NOT AVAILABLE. |
| **Set GLOBAL `log_bin_trust_function_creators=1`** | `bootstrap_service.yml:2-17`, logged in as `glance_database_shard_root_user` (the DB root user without ProxySQL, `defaults/main.yml:125`), unless `use_preconfigured_databases` | **yes, on every deploy/reconfigure** |
| `bootstrap_glance` container, `KOLLA_BOOTSTRAP`: `glance-manage db_sync` then `glance-manage db_load_metadefs` (kolla `docker/glance/glance-api/extend_start.sh:5-9`) | `bootstrap_service.yml:19-37`, delegate `glance_api_hosts[0]` | **yes, so a schema sync runs on every reconfigure** |
| Set `log_bin_trust_function_creators=0` | `bootstrap_service.yml:39-54` | yes |
| Keystone: service `glance`/`image`, 2 endpoints (internal, public), user `glance` (admin in `service`) | `tasks/register.yml:2-7`; `defaults/main.yml:92-104` | yes (deploy/reconfigure); **not** on upgrade |

**Oddity / risk:** the enable/db_sync/disable sequence is still not wrapped in `block/always`. If the bootstrap
container fails, the global MariaDB variable stays at `1`. Whether this leftover state has security consequences is NOT
AVAILABLE. A related upstream fix for keystone appears in
`releasenotes/notes/bug-1987982-fix-keystone-log_bin_trust_function_creators-variables-8628098891513dac.yaml`.

**Reconfigure as uncontrolled upgrade:** if an operator bumps `openstack_tag`/`glance_tag` and runs `reconfigure`, the
new image runs the `KOLLA_BOOTSTRAP` branch (`glance-manage db_sync` and `db_load_metadefs`, kolla
`docker/glance/glance-api/extend_start.sh:5-9`) and the handler recreates glance-api on the new image. For the glance
role that is the default legacy upgrade (`glance_enable_rolling_upgrade: "no"`, `all.yml:1008`):
`legacy_upgrade.yml:2-9` runs the same config, check-containers, `bootstrap_service.yml` and flush steps, and
reconfigure only adds registration, DB/user creation and the dev-mode clone (`deploy.yml:2-15`).

### 1.7 Dependencies (from `templates/glance-api.conf.j2`)

- **MariaDB** via the VIP (:34-38); **RabbitMQ**: `transport_url = rpc_transport_url` (:27) and notifications (:118-125;
  topic `notifications` only if ceilometer, otherwise `driver = noop`, `defaults/main.yml:109-113`).
  `[oslo_messaging_rabbit]` gains `rabbit_quorum_queue = true` by default and, with the off-by-default queue manager,
  `use_queue_manager` (:127-148).
- **Keystone**: `www_authenticate_uri` and `auth_url` are both `keystone_internal_url` (:40-51). **memcached**: all
  hosts (:53-55).
- **Cinder**: `cinder_catalog_info = volume:cinder:internalURL` (:25), and `enabled_backends` contains `cinder:cinder`
  whenever `enable_cinder` (`defaults/main.yml:233-235`; template :17-19). **Oddity, still holds in 2024.1:** cinder
  registers only `cinderv3/volumev3` (`roles/cinder/defaults/main.yml:335-341`). No `volume/cinder` catalog entry
  exists, and the template has no `[cinder]` store section, so the glance cinder store is enabled without a matching
  catalog entry or store section. Whether it works if used is NOT AVAILABLE. Nova, by contrast, uses
  `catalog_info = volumev3:cinderv3:internalURL` (`roles/nova-cell/templates/nova.conf.j2:113`).
- **Ceph**: changed in 2024.1, one `[<backend name>]` section per entry of `glance_ceph_backends` (default `[rbd]`),
  with `rbd_store_user/pool` and the new `rbd_store_ceph_conf = /etc/ceph/<cluster>.conf` (:68-75). The template still
  does not set `show_multiple_locations` (`grep -rn show_multiple_locations ansible/roles/glance` → nothing).
- **Default store**: changed in 2024.1, `default_backend = "{{ glance_default_backend }}"` (:60-61), where
  `glance_default_backend` picks vmware, then the first Ceph backend, then swift, then s3, then file
  (`defaults/main.yml:247`). The value is rendered between double quotes; how glance's config parser reads the quotes is
  NOT AVAILABLE.
- **Swift**: `[swift]` section (:77-87) with **`swift_store_auth_insecure = True` hard-coded**. `glance-swift.conf`
  authenticates against `openstack_auth.auth_url` (= `keystone_internal_url`, `all.yml:990-991`) as `service:glance`
  (`templates/glance-swift.conf.j2:1-8`).
- **S3** (new in 2024.1): `[s3]` with `s3_store_host/access_key/secret_key/bucket` from `glance_backend_s3_*`, which
  default to the global `s3_url`, `s3_bucket`, `s3_access_key`, `s3_secret_key` (:89-95; `defaults/main.yml:145-148`;
  `all.yml:1282-1285`).
- **Barbican** (:163-168), **osprofiler** (:155-161), **VMware** (:97-104). New in 2024.1:
  `[cors] allowed_origin = {{ horizon_public_endpoint }}` (:170-171).
- Cinder iSCSI flag toggles glance-api `/dev` and `iscsi_info`, and cinder iSCSI or `cinder_backend_ceph` toggles
  `privileged` (`defaults/main.yml:10,202-203`). The code comment says the mounts are "to support Cinder iSCSI backends"
  (`defaults/main.yml:201`). How glance uses these mounts is NOT AVAILABLE.

### 1.8 Operational notes

1. **Backend switch via unrelated flags:** `glance_backend_swift` defaults to `enable_swift` (`all.yml:1006`), and
   `glance_backend_file` is the negation of ceph/s3/swift/vmware (`all.yml:1001`). Enabling Swift (or
   `glance_backend_ceph`, or the new `glance_backend_s3`) on a running cloud does three things:
   - removes `file` from `enabled_backends` and drops the `[file]` section (`defaults/main.yml:224-226`; template
     :17-19,63-66);
   - changes `default_backend` (`defaults/main.yml:247`; template :60-61);
   - expands `glance_api_hosts` to every `glance-api` host (`all.yml:1011`).

   NOT AVAILABLE: whether existing images in the file store stay readable after the switch.

   A related doc mismatch, still present: the guide says ceph is enabled "automatically" (`glance-guide.rst:43`), but
   the default is `glance_backend_ceph: "no"` (`all.yml:1002`).
2. **Inventory order matters:** with the file backend, glance runs on `groups['glance-api']|first`. The INI parser reads
   the file line by line and adds each host in that order, and Ansible lists a group's hosts in the order they were
   added (ansible-core 2.16.20 `lib/ansible/plugins/inventory/ini.py:160,215-217`,
   `lib/ansible/plugins/inventory/__init__.py:205-210`, `lib/ansible/inventory/group.py:231-237,280-292`,
   `lib/ansible/inventory/data.py:258-268`), so reordering the inventory moves glance-api to another host, and the
   HAProxy members follow it (`all.yml:1011`; `defaults/main.yml:86-87`). NOT AVAILABLE: what the `glance` volume on the
   new host contains.
3. **Restart impact:** the HAProxy client and server timeouts are 6h (`defaults/main.yml:139-140`). Restarting
   glance-api stops it with the 60 s graceful timeout ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). With the
   file backend this is a total Image API outage, because glance-api is the only backend
   ([§1.2](#12-glance_services-ansiblerolesglancedefaultsmainyml2-64)). NOT AVAILABLE: what the restart does to
   in-flight uploads, downloads, nova snapshots and cinder upload-to-image operations, whether images are left in
   `saving`/`queued`, and whether nova boots that need an uncached image fail during the window.
4. **Rolling upgrade** (`tasks/rolling_upgrade.yml`), unchanged in 2024.1:
   - Sequence: config on host[0] (:7-8) → **stop glance-api on host[0]** (:10-11, `stop_service.yml`) → enable log_bin
     (:13-28) → `GLANCE_DB_EXPAND` (:30-49) → `GLANCE_DB_MIGRATE`, which notifies restart (:51-73) → config on the other
     hosts (:75-76) → check-containers (:78) → **flush handlers**, so all glance-api containers restart in the same
     handler run (:80-81) → `GLANCE_DB_CONTRACT` (:83-102) → disable log_bin (:104-119).
   - The `glance_upgrading` fact (:2-4, :121-123) is set but never read anywhere (dead code;
     `grep -rn glance_upgrading ansible/` finds only this file).
   - With `kolla_serial` > 0, each batch re-runs the run_once expand/migrate/**contract** on `glance_api_hosts[0]`
     (:48-49, :69-70, :101-102), because Ansible runs the play once per batch and sends a `run_once` task to the first
     host of each batch ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). The contract therefore runs at the end
     of batch 1, while hosts in later batches still run the old glance-api containers.
   - The docs warn that rolling upgrade with a non-shared file backend leads to "a corrupt state"
     (`glance-guide.rst:134-136`).
5. **Image cache** is never pruned. The docs say "Glance caches are not cleaned up automatically"
   (`glance-guide.rst:173`); there is no cron/pruner container.
6. **Sanity check** (if enabled) creates and deletes an image on every deploy/reconfigure. Not available in 2024.1: the
   role has no `check.yml`, `tasks/deploy.yml:1-15` has no check step, and `kolla_enable_sanity_glance` is not defined
   ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).
7. Glance does not touch compute hosts. Nova-compute reaches glance through `[glance] api_servers` =
   `glance_internal_endpoint` (internal FQDN, port 9292, `all.yml:1015`;
   `roles/nova-cell/templates/nova.conf.j2:105-109`), and cinder through `glance_api_servers`
   (`roles/cinder/templates/cinder.conf.j2:18`).

---

## 2. PLACEMENT

### 2.1 Play

```yaml
# ansible/site.yml:593-605
- name: Apply role placement
  gather_facts: false
  hosts: [placement-api, '&enable_placement_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ placement_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: placement, tags: placement }]
```
- `enable_placement: "{{ enable_nova | bool or enable_zun | bool }}"` (`all.yml:837`).
- **Oddity, still holds in 2024.1:** the LB include for placement **has no `when: enable_placement`**
  (`site.yml:248-251`), unlike every other service. When placement is disabled it still writes an (effectively empty)
  `services.d/placement-api.cfg`, because `placement-api.enabled: True` (`roles/placement/defaults/main.yml:7`) and the
  haproxy-config task checks only `service.enabled`, `service.haproxy` and `enable_haproxy`
  (`roles/haproxy-config/tasks/main.yml:17-20`). Only the inner haproxy entries carry `enable_placement`
  (`roles/placement/defaults/main.yml:13,20`), and the template skips disabled entries
  (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:121`).
- The play sits right before `import_playbook: nova.yml` (`site.yml:609`).

### 2.2 `placement_services` (`ansible/roles/placement/defaults/main.yml:2-24`)

In 2024.1 the dict is at `ansible/roles/placement/defaults/main.yml:2-26`.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| placement-api | `placement_api` | `placement-api` | `True` | Plain Apache/mod_wsgi. No privileged, no host paths beyond config, localtime, timezone (Debian) and logs, plus the dev-mode source (:80-85). Unlike glance, cinder and heat it gets no `/dev/shm` entry. HAProxy internal and external on 8780, `tls_backend: placement_enable_tls_backend` (:11-26); the external entry now names `external_fqdn` and `placement_api_public_port` (:23-24). |

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
| `placement-api/placement-api-wsgi.conf` | first_found: `placement/<host>/placement-api-wsgi.conf` → `placement/placement-api-wsgi.conf` → template (:71-87). Changed in 2024.1: the template's `ErrorLog` is `placement-api-error.log` (`templates/placement-api-wsgi.conf.j2:31`), so the file changes on the first 2024.1 run. | Restart |
| `placement-api/migrate-db.rc` | `migrate-db.rc.j2` (:89-101) | Restart |
| policy | `{{node_custom_config}}/placement/` (:15-32, :103-115) | Restart |
| certs | service-cert-copy (:34-36) | Restart |

`migrate-db.rc` still contains the **nova_api DB user and password** together with the placement DB creds
(`templates/migrate-db.rc.j2:1-8`; vars at `defaults/main.yml:122-125`). The defaults file files these vars under
"Upgrade" (`defaults/main.yml:119-121`); no task of the role uses it, and the container receives it as
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
  `defaults/main.yml:130-142`) happens in deploy, reconfigure **and upgrade** (`upgrade.yml:2`), unlike glance and heat.
- Online data migrations: the separate `KOLLA_OSM` container runs **only** in upgrade (`upgrade.yml:16-34`). Because the
  bootstrap container above also runs `db online_data_migrations`, placement OSM also runs on every deploy/reconfigure
  (`deploy.yml:11`, `reconfigure.yml:2`) and twice in upgrade (bootstrap at `upgrade.yml:11`, then `KOLLA_OSM`).

### 2.7 Dependencies (`templates/placement.conf.j2`)

- MariaDB `[placement_database]` with **`max_overflow = 1000` hard-coded** (:14-19).
- memcached `[cache]` and `keystone_authtoken` (:21-42); Keystone (:27-38).
- The template sets no `transport_url` (placement does no RPC).
- `[DEFAULT]` holds only debug, log and state paths (:1-6).
- **Dead variables:** `placement_notification_topics` / `placement_enabled_notification_topics`
  (`defaults/main.yml:104-108`) are not referenced by any template. There is no `[oslo_messaging_notifications]`
  section.

### 2.8 Operational notes and the relation to nova

- **Consumers authenticate as the placement user.** nova-api/conductor/scheduler
  (`roles/nova/templates/nova.conf.j2:192-202`) and **nova-compute on every compute host**
  (`roles/nova-cell/templates/nova.conf.j2:234-244`) use `username = {{ placement_keystone_user }}` /
  `password = {{ placement_keystone_password }}`, `valid_interfaces = internal`. Neutron does the same with
  `endpoint_type = internal` (`roles/neutron/templates/neutron.conf.j2:196-206`), as does cyborg
  (`roles/cyborg/templates/cyborg.conf.j2:34-38`); zun does not (its `[placement_client]` has no credentials,
  `roles/zun/templates/zun.conf.j2:92-95`). Rotating `placement_keystone_password` therefore needs a reconfigure of
  placement **and** nova (all computes) **and** neutron. This dependency scales with the number of compute hosts.
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
# ansible/site.yml:576-591
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
  (`all.yml:750-754`). `cinder_backend_ceph: "no"`, `cinder_backup_driver: "ceph"` (`all.yml:1041,1050`).
- Sample inventory: `cinder-api`/`cinder-scheduler` sit under `[cinder:children] control`.
  **`cinder-volume`/`cinder-backup` sit under `storage`** (`ansible/inventory/multinode:110-111,285-295`).

### 3.2 `cinder_services` (`ansible/roles/cinder/defaults/main.yml:2-48`)

In 2024.1 the dict is at `ansible/roles/cinder/defaults/main.yml:2-54`.

| key | container | group | enabled | flags / host volumes |
|---|---|---|---|---|
| cinder-api | `cinder_api` | cinder-api | true | Apache/mod_wsgi on 8776; HAProxy internal and external (:11-26) |
| cinder-scheduler | `cinder_scheduler` | cinder-scheduler | true | – |
| cinder-volume | `cinder_volume` | cinder-volume | true | **`privileged: True`, `ipc_mode: host`** (:40-41), `tmpfs` for `/var/lib/cinder/conversion` only if `cinder_enable_conversion_tmpfs` (default false, :42,206-210). Volumes (:187-198, plus `run_default_volumes_<engine>`, empty for Docker, :43): **`/dev/:/dev/`, `/lib/modules:ro`, `/run:/run:shared`** (`:shared` only with Docker), `cinder:/var/lib/cinder`, **`iscsi_info:/etc/iscsi`** (if `enable_iscsid`), **`target_config:/etc/target`** (LVM and `lioadm`). |
| cinder-backup | `cinder_backup` | cinder-backup | `enable_cinder_backup` | **`privileged: True`** (no ipc host). Volumes (:169-179, plus `run_default_volumes_<engine>`, :52): `/dev/`, `/lib/modules`, `/run` (`:shared` with Docker), `cinder:/var/lib/cinder`, `iscsi_info`. |

Related: `cinder_target_helper` is `lioadm` on RedHat and `tgtadm` otherwise (`all.yml:1045`). With `tgtadm` the targets
are served by a **separate `tgtd` container** from the `iscsi` role, which also deploys `iscsid` on `compute`,
`cinder-volume` and `cinder-backup` hosts (`roles/iscsi/defaults/main.yml:2-20,62-73`; play `site.yml:439-452`).

### 3.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`tasks/deploy.yml:1-14`). There is no `check.yml` step. |
| upgrade | `config.yml` **only on `groups['cinder-api'][0]`** (:4-5) → `bootstrap_service.yml` (db sync, new image, old services still running) (:7) → `config.yml` on all (:9) → `check-containers.yml` (:11) → `service-ks-register` for the cinder user's `service` role grant only (:13-18; changed in 2024.1: it no longer creates the `service` role, and a comment says to remove the task in the next cycle) → flush, so **every cinder container on every host restarts in this flush (serial 0)**, cinder-volume and cinder-backup included; on upgrade a handler then pauses `cinder_rpc_version_startup_delay` (30 s) once (:20-21; `handlers/main.yml:70-88`; `defaults/main.yml:232`) → **`reload.yml`: `restart_container` of every enabled cinder container on the host again, "to remove RPC version pin"** (:23; `tasks/reload.yml:2-10`) → `KOLLA_OSM` online migrations (:25-43). No `register.yml`, so services and endpoints are not refreshed. |
| deploy-containers | check-containers |
| pull / stop | helpers |
| precheck | groups; API port free; **at least one backend enabled** unless `skip_cinder_backend_check` (:28-44); **`vgs cinder-volumes`** on cinder-volume hosts if LVM (:46-56); new in 2024.1, an assert on the four `cinder_backup_s3_*` variables when `cinder_backup_driver == "s3"` (`tasks/precheck.yml:58-68`) |
| check | Not available in 2024.1: the role has no `check.yml`, and `kolla_enable_sanity_cinder` is not defined ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). |
| config | `config.yml` |

### 3.4 Config files (`ansible/roles/cinder/tasks/config.yml`)

| dest | sources | when | notifies |
|---|---|---|---|
| `cinder-volume/ceph/`, `cinder-backup/ceph/` dirs | `file`, mode 0770 (`external_ceph.yml:2-17`) | `cinder_backend_ceph` and host in volume/backup (`config.yml:15-19`) | – |
| `<svc>/ceph/<cluster>.conf` (cinder-volume, cinder-backup) | **changed in 2024.1:** merge `cinder/<cluster>.conf` + `cinder/<svc>/<cluster>.conf`, once per service and per entry of `cinder_ceph_backends` (default one entry `rbd-1`, cluster `ceph`, `defaults/main.yml:270-273`) (`external_ceph.yml:19-42`). In 2023.1 the sources were `cinder/ceph.conf` + `cinder/<svc>/ceph.conf` and the destination `<svc>/ceph.conf`. | `cinder_backend_ceph` and host in volume/backup | Restart `<svc>` |
| `cinder-volume/ceph/<cluster>.<ceph_cinder_keyring>` | `cinder/cinder-volume/<cluster>.client.cinder.keyring` (`external_ceph.yml:44-58`; `all.yml:1182`) | cephx | Restart cinder-volume |
| `cinder-backup/ceph/` keyrings (cinder plus cinder-backup) | `cinder/cinder-backup/<cluster>.client.cinder.keyring` and `.client.cinder-backup.keyring`, cluster of `cinder_backup_ceph_backend` (`external_ceph.yml:60-75`; `defaults/main.yml:275-276`; `all.yml:1182-1183`) | cephx | Restart cinder-backup |
| policy | `{{node_custom_config}}/cinder/` (:21-38, :110-122) | | Restart `<svc>` |
| certs | service-cert-copy (:40-42) | | |
| `<svc>/config.json` | `<svc>.json.j2` (:44-55) | | Restart `<svc>` |
| `cinder-api/cinder-wsgi.conf` | first_found: `cinder/<host>/cinder-wsgi.conf` → `cinder/cinder-wsgi.conf` → template (:57-73) | | Restart cinder-api |
| `<svc>/cinder.conf` (one per service, `service_name` var) | merge: template → `global.conf` → `cinder.conf` → `cinder/<svc>.conf` → `cinder/<host>/cinder.conf` (:75-93) | | Restart `<svc>` |
| `cinder-volume/hostnqn` (new in 2024.1) | template `hostnqn.j2`, value `nqn.2014-08.org.nvmexpress:uuid:<to_uuid of the host name>` (:95-108); copied into the container as `/etc/nvme/hostnqn`, owner root (`templates/cinder-volume.json.j2:23-28`) | host in cinder-volume | Restart cinder-volume |
| `cinder-volume/nfs_shares` | first_found among 8 paths (`nfs_shares.j2` variants, then plain), `skip` unless NFS or HNAS (:124-143) | host in cinder-volume | Restart cinder-volume |

Because the Ceph files move into `ceph/` (copied to `/etc/ceph` by `templates/cinder-volume.json.j2:9-15` and
`templates/cinder-backup.json.j2:15-21`) and `hostnqn` is a new file, the first 2024.1 deploy/reconfigure changes the
config of every cinder-volume (and, with Ceph, cinder-backup) and notifies its restart.

### 3.5 Handlers (`ansible/roles/cinder/handlers/main.yml`)

Four restart handlers (api :2-16, scheduler :18-32, volume :34-51, backup :53-68), all recreate_or_restart. The volume
handler passes `privileged`, `ipc_mode` and `tmpfs`; the backup handler passes `privileged`. A fifth handler,
`Wait for cinder services to update service versions` (:78-88), listens to all four and pauses 30 s once, only when
`kolla_action == 'upgrade'`. There is no drain logic. Unchanged in 2024.1 apart from the module name.

### 3.6 Bootstrap

- `mysql_db cinder` and `mysql_user` run every deploy/reconfigure (`bootstrap.yml:2-36`).
- `bootstrap_cinder` (`KOLLA_BOOTSTRAP`: `cinder-manage db sync`, kolla `docker/cinder/cinder-api/extend_start.sh:6-9`),
  run_once on `groups['cinder-api'][0]` (`bootstrap_service.yml:2-20`). **It re-runs on every reconfigure.**
- Online data migrations (`KOLLA_OSM`) run only in upgrade.
- Keystone: only `cinderv3/volumev3`, with 2 `/v3/%(tenant_id)s` endpoints (internal, public); user `cinder` (admin in
  `service`); the `service` role granted to the cinder user in the `service` project
  (`defaults/main.yml:218-219,335-352`; `tasks/register.yml:2-8`). Changed in 2024.1: the role no longer passes
  `service_ks_register_roles`, so it no longer creates the `service` role itself (`service_ks_register_roles` defaults
  to `[]`, `roles/service-ks-register/defaults/main.yml:29`; roles created at
  `roles/service-ks-register/tasks/main.yml:87-97`). Which component creates the `service` role before the grant in
  2024.1 is NOT AVAILABLE from these roles. Services and endpoints are registered on deploy/reconfigure, not on upgrade.

### 3.7 Dependencies (`templates/cinder.conf.j2`)

- **Glance**: `glance_api_servers` = `glance_internal_endpoint` (internal FQDN, port 9292) (:18).
  **`glance_num_retries = {{ groups['glance-api'] | length }}`** (:20) scales with the number of glance hosts. With the
  glance file backend only one glance-api exists, yet retries equal the group size.
- **Nova**: `[nova]` section authenticates with **`nova_keystone_user`/`nova_keystone_password`** (:109-119), so
  rotating the nova password needs a cinder reconfigure. In the other direction, nova-api and nova-compute use
  **`cinder_keystone_user/password`** (`roles/nova-cell/templates/nova.conf.j2:112-121`,
  `roles/nova/templates/nova.conf.j2:66-75`), so rotating the cinder password needs a reconfigure of all computes.
  Manila also uses the cinder creds (`roles/manila/templates/manila-share.conf.j2:29-30`).
- MariaDB (:121-125); RabbitMQ RPC (:64) and notify (:66-73; topic `notifications` for ceilometer only,
  `defaults/main.yml:285-289`; the 2023.1 vitrage topic is gone with the vitrage role); `[oslo_messaging_rabbit]` with
  quorum queues by default (:75-99); Keystone and memcached (:127-146); Barbican (:264-269); osprofiler (:256-262).
- **Ceph**: changed in 2024.1, one section per entry of `cinder_ceph_backends` (default `[rbd-1]`) with
  `rbd_ceph_conf = /etc/ceph/<cluster>.conf`, the new `rbd_cluster_name` and `rbd_keyring_conf`, an optional
  `backend_availability_zone`, and `rbd_secret_uuid = cinder_rbd_secret_uuid` (:161-178). The same UUID is installed
  into libvirt on computes by `roles/nova-cell/tasks/external_ceph.yml:169,194`, so the two must stay in sync.
- **Backup drivers**: ceph (`backup_ceph_conf = /etc/ceph/<cluster of cinder_backup_ceph_backend>.conf`), nfs, swift
  (`backup_swift_url` internal) and, new in 2024.1, s3 (:27-58).
- **Coordination**: redis or etcd (:271-281). The etcd URL is
  `etcd3+<internal_protocol>://{{ kolla_internal_fqdn }}:{{ etcd_client_port }}?api_version=v3` (:280; the
  `?api_version=v3` query is new in 2024.1), and the etcd role defines an internal HAProxy entry on `etcd_client_port`
  (`roles/etcd/defaults/main.yml:11-17`), so cinder reaches etcd through the internal VIP. Default
  `cinder_coordination_backend` is `''` unless redis or etcd is enabled (`all.yml:1047`; `enable_etcd: "no"`,
  `enable_redis: "no"`, `all.yml:764,840`).
- **LVM/iSCSI**: `target_helper`, `target_protocol = iscsi` (:152-159).

### 3.8 Operational notes

1. **No `host`/`backend_host`/`cluster` set in cinder.conf** (`templates/cinder.conf.j2` has none;
   `grep backend_host ansible/roles/cinder` returns nothing). Because of `network_mode: host`, each cinder-volume
   container has the node hostname ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Whether cinder then registers
   it as `<node-hostname>@<backend>` is upstream cinder behaviour and NOT AVAILABLE here.
   - NOT AVAILABLE (upstream cinder): whether, with a shared backend (ceph `rbd-1`) on several cinder-volume hosts,
     every volume is owned by the host that created it.
   - NOT AVAILABLE: whether, if that node is down, its volumes cannot be attached, detached, deleted or snapshotted
     until the node returns or `cinder-manage volume update_host` is run.
   - The same question applies to renaming or replacing a storage node. The new `hostnqn` is also derived from the host
     name (`tasks/config.yml:98`), so a renamed node gets a new NQN. The docs also note LVM issues in a multi-controller
     setup (`doc/source/reference/storage/cinder-guide.rst:52-55`).
2. **cinder-volume restart impact** (upstream cinder and os-brick behaviour, NOT AVAILABLE beyond the code facts):
   - Code facts: with LVM, the LIO config is kept in the `target_config` volume (`defaults/main.yml:196`) or the targets
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
4. **Upgrade restarts every cinder-volume and cinder-backup at once, twice** (flush at `upgrade.yml:20-21`, then
   `reload.yml` at `upgrade.yml:23`; serial 0 unless `ANSIBLE_SERIAL` is set). There is no `[upgrade_levels]` pinning in
   the template. The code comment explains the second restart: after an upgrade, services keep an RPC version cap until
   all of them are restarted, and the role waits 30 s for the services to update their version in the database
   (`handlers/main.yml:70-76`). The `reload.yml` restart is a plain `restart_container`, without
   `when: kolla_action != "config"` or any other condition, on every enabled cinder service mapped to the host
   (`tasks/reload.yml:2-10`). NOT AVAILABLE: whether 30 s is enough on a given cloud, and whether in-flight operations
   survive two restarts in a row.
5. **Oddity: backup driver vs. ceph files**, still holds in 2024.1. `cinder_backup_driver: "ceph"` is the default even
   when `cinder_backend_ceph` is `no`. cinder.conf then sets `backup_driver = ...CephBackupDriver`,
   `backup_ceph_conf=/etc/ceph/ceph.conf` (:28-36; the cluster of `cinder_backup_ceph_backend` is `ceph` even when the
   backend is disabled, `defaults/main.yml:270-276`). But `cinder-backup.json.j2` only copies the `ceph` directory
   `{% if cinder_backend_ceph %}` (:15-21), and `external_ceph.yml` only runs for `cinder_backend_ceph`
   (`config.yml:15-19`). With an LVM or NFS-only deployment and default backup settings, kolla-ansible therefore gives
   cinder-backup no ceph config. Whether its driver then fails is NOT AVAILABLE.
6. **Multipath** is never configured on the cinder side: no `use_multipath_for_image_xfer` / `volume_use_multipath` in
   the cinder templates (`grep multipath ansible/roles/cinder` returns nothing). On the nova side,
   `volume_use_multipath = True` is set in nova-compute's libvirt config when `enable_multipathd` is on
   (`roles/nova-cell/templates/nova.conf.d/libvirt.conf.j2:27-28`). The `multipathd` container is off by default
   (`all.yml:809`).
7. **Compute-host touchpoints:** the cinder role itself does not target computes. However, `iscsid` on computes (iscsi
   role) shares `iscsi_info`, nova-compute uses the cinder creds, and the RBD secret is shared with nova-libvirt.
   Enabling `enable_cinder_backend_iscsi`/LVM also flips glance-api to privileged with `/dev`, so **glance-api is
   recreated** (`roles/glance/defaults/main.yml:10,202-203`). `cinder_backend_ceph` (with Cinder enabled) also makes
   glance-api privileged, without `/dev` (`roles/glance/defaults/main.yml:10`).
8. External Ceph needs cinder-volume and cinder-backup hosts in the `storage` group, otherwise "Cinder and related
   services relying on this group [will] fail" (`doc/source/reference/storage/external-ceph-guide.rst:146-155`).
9. The sanity check (if enabled) creates a 1 GB volume on every deploy/reconfigure. Not available in 2024.1: the role
   has no `check.yml` ([§3.3](#33-task-flow)).

---

## 4. HORIZON

### 4.1 Play

```yaml
# ansible/site.yml:740-752
- name: Apply role horizon
  gather_facts: false
  hosts: [horizon, '&enable_horizon_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ horizon_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: horizon, tags: horizon }]
```
- LB include: `site.yml:188-192`. `enable_horizon: "{{ enable_openstack_core | bool }}"` (`all.yml:773`).
- Horizon is the last of these plays.

### 4.2 `horizon_services` (`ansible/roles/horizon/defaults/main.yml:2-69`)

In 2024.1 the dict is at `ansible/roles/horizon/defaults/main.yml:2-73`.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| horizon | `horizon` | horizon | true | **`environment`: 16 `ENABLE_<PLUGIN>` flags plus `FORCE_GENERATE`** (:8-25). Changed in 2024.1: the freezer, murano, sahara, senlin, solum and vitrage flags are gone with their roles, and `ENABLE_FWAAS` is new (:12). There is **no host `/tmp` bind**: the volumes are config, dev-mode sources, localtime, timezone and logs (:123-129). Settings use `LOCAL_PATH = '/tmp'` (`templates/_9998-kolla-settings.py.j2:43`), which is therefore the container's own `/tmp`. HAProxy uses `balance roundrobin` when `enable_memcached` or `horizon_backend_database`, `balance source` otherwise (:39, :59; `enable_memcached: "yes"`, `all.yml:729`, so `roundrobin` by default). Redirect frontends (`mode: redirect`, port 80) are added when internal or external TLS is on (:41-48, :61-69), and an `acme_client` backend is defined (:70-73); new in 2024.1, every frontend routes `/.well-known/acme-challenge/` to it (:37, :48, :57, :69). |

Because the plugin flags live in the container environment, and `check-containers` compares `environment`
(`tasks/check-containers.yml:11`), **enabling or disabling any service that has a horizon plugin** (designate, octavia,
magnum, …) changes the env. The horizon container is then **recreated** on the next deploy/reconfigure even if no
horizon config changed. On the first 2024.1 run the removed flags alone change the environment of a container created by
2023.1.

### 4.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` **only if `horizon_backend_database`** → flush (`tasks/deploy.yml:1-14`). There is **no keystone registration**. |
| upgrade | `config.yml` → `check-containers.yml` → (clone) → `bootstrap_service.yml` if DB backend → flush (`tasks/upgrade.yml:1-14`) |
| precheck | groups; `horizon_listen_port` free (80, or 443 when `horizon_enable_tls_backend`; `all.yml:423-425`) (`tasks/precheck.yml:16-27`) |
| check | empty (`tasks/check.yml:1`) |
| pull / stop / deploy-containers / config | standard |

### 4.4 Config files (`ansible/roles/horizon/tasks/config.yml`)

| dest | source | notifies |
|---|---|---|
| per-service policy files (`<svc>_policy.json/yaml`) | for each enabled service in the list (:19-41), `policy_item.yml` looks for `{{node_custom_config}}/horizon/<svc>_<policy file>` (`tasks/policy_item.yml:3-25`) and copies the matches (:111-124) | Restart horizon |
| `horizon/config.json` | `horizon.json.j2` (:43-55) | Restart horizon |
| `horizon/horizon.conf` (Apache) | first_found: `horizon/<host>/horizon.conf` → `horizon/horizon.conf` → template (:57-73). This is a **whole-file override**, not a merge. | Restart horizon |
| `horizon/_9998-kolla-settings.py` | **changed in 2024.1** (was `local_settings`): first_found: `horizon/<host>/_9998-kolla-settings.py` → `horizon/_9998-kolla-settings.py` → `_9998-kolla-settings.py.j2` (:75-91). Whole-file override. | Restart horizon |
| `horizon/_9999-custom-settings.py` | **changed in 2024.1** (was `custom_local_settings`): first_found, same pattern; the default template is empty (:93-109; `templates/_9999-custom-settings.py.j2` has 0 lines). | Restart horizon |
| custom themes | `{{node_custom_config}}/horizon/themes/<name>` for each `horizon_custom_themes` entry (default `[]`, `defaults/main.yml:78`) (:126-140) | Restart horizon |
| certs | service-cert-copy (:142-144) | |

**Changed in 2024.1, the settings layout:** `horizon.json.j2` copies both files into
`/etc/openstack-dashboard/local_settings.d/` (`templates/horizon.json.j2:21-32`) instead of replacing
`/etc/openstack-dashboard/local_settings`. The base `local_settings.py` is now the one the image ships: the kolla image
copies Horizon's `local_settings.py.example` to `/etc/openstack-dashboard/local_settings.py` and links the dashboard's
`local_settings.d` to `/etc/openstack-dashboard/local_settings.d` (kolla `docker/horizon/Dockerfile.j2:56-65`).
Consequences read from the code:

- An operator override kept under the old names (`/etc/kolla/config/horizon/local_settings` or `custom_local_settings`)
  is no longer looked up (`tasks/config.yml:83-86,101-104`): it is silently ignored on the first 2024.1 run.
- `_9998-kolla-settings.py` is a fragment, not a full settings file: it assigns into `CACHES['default']`
  (`templates/_9998-kolla-settings.py.j2:21-22`), so it relies on the base settings defining `CACHES`. How Horizon loads
  `local_settings.d` (order, error handling) is upstream Horizon behaviour and NOT AVAILABLE.

### 4.5 Handlers

`Restart horizon container` (`handlers/main.yml:2-17`): recreate_or_restart. It passes `environment`; there is no other
logic.

### 4.6 Bootstrap

- Changed in 2024.1: `horizon_backend_database: false` (`all.yml:1141`); in 2023.1 it followed `enable_murano`, a role
  that no longer exists. Only when an operator sets it does deploy/reconfigure create the DB and user and run
  `bootstrap_horizon` (`KOLLA_BOOTSTRAP`: Django `manage.py migrate --noinput`, then exits; kolla
  `docker/horizon/extend_start.sh:27-30`) (`tasks/bootstrap.yml:2-38`, `bootstrap_service.yml:2-20`). In that case **the
  bootstrap re-runs on every reconfigure**.
- There is no keystone registration at all.

### 4.7 Dependencies (`templates/_9998-kolla-settings.py.j2`)

In 2024.1 the dependencies are read in `_9998-kolla-settings.py.j2`; `local_settings.j2` no longer exists.

- **Keystone**: `OPENSTACK_KEYSTONE_URL = "{{ horizon_keystone_url }}/v3"` (template :58), with `horizon_keystone_url` =
  `keystone_internal_url`, or `keystone_public_url` when `horizon_use_keystone_public_url` (default False)
  (`defaults/main.yml:137,160`). `OPENSTACK_HOST = kolla_internal_fqdn` (:56). `OPENSTACK_ENDPOINT_TYPE = "internalURL"`
  (:131), so Horizon talks to **every** service's internal endpoint from its own container.
- **memcached**: `SESSION_ENGINE = cache` with all memcached hosts, `ignore_exc: True`, **unless** the DB backend is
  used (:19-23). With the DB backend: `SESSION_ENGINE = db` plus MariaDB (:7-18). Changed in 2024.1: the cache branch is
  chosen when `groups['memcached']` is not empty, not from `enable_memcached` (:19), while the HAProxy balance still
  follows `enable_memcached` ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)).
- **Cinder**: `enable_backup` follows `enable_cinder_backup` (:98-100). The 2023.1 Murano/Barbican `KEY_MANAGER` block
  is gone with the murano role.
- `SECRET_KEY = horizon_secret_key` (:44), which is the same on all nodes.
- Multi-region `AVAILABLE_REGIONS` (:48-54).
- TLS: `SECURE_PROXY_SSL_HEADER` and secure cookies when either internal or external TLS is on (:25-29).
  `horizon.conf.j2` only handles `horizon_enable_tls_backend` (`templates/horizon.conf.j2:3,43`), and the http→https
  redirects are HAProxy entries ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)).

### 4.8 Operational notes

- Sessions live in memcached unless the DB backend is used (`_9998-kolla-settings.py.j2:7-23`), HAProxy uses
  `balance roundrobin` by default and `balance source` only when memcached is disabled and the DB backend is not used
  ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)), and `LOCAL_PATH=/tmp` is the **container's**
  `/tmp`, so it does not survive a recreate ([§4.2](#42-horizon_services-ansibleroleshorizondefaultsmainyml2-69)). NOT
  AVAILABLE: whether a horizon restart or a **memcached restart** logs users out, what restarting a node does to
  in-flight requests (including image uploads, `HORIZON_IMAGES_UPLOAD_MODE = 'direct'` at
  `_9998-kolla-settings.py.j2:130`), and whether anything is staged in `LOCAL_PATH`.
- Image side (kolla `docker/horizon/extend_start.sh`): every start syncs each `ENABLE_<PLUGIN>` dashboard file into
  `openstack_dashboard/local/enabled` (`:32-46,225-241`). `manage.py collectstatic --noinput --clear` and
  `compress --force` run **only** when `/var/lib/kolla/.settings.md5sum.txt` is missing, the md5 of `local_settings` +
  `custom_local_settings` + `local_settings.d` differs from it, a plugin file was just copied in or removed, or
  `FORCE_GENERATE=yes` (`:38-45,206-223,243-259`). The kolla-ansible files now sit in `local_settings.d`, which the hash
  covers (`:209-212`). New in 2024.1: `compress` is tried up to 5 times and the start script exits 1 if all attempts
  fail (`:245-257`). kolla-ansible sets `FORCE_GENERATE=yes` only when `horizon_dev_mode` is on, and `no` otherwise
  (`defaults/main.yml:25,153`). The settings set `COMPRESS_OFFLINE = True` (`_9998-kolla-settings.py.j2:3`).
  `/var/lib/kolla` is not a volume (`defaults/main.yml:123-129`), so the hash file lives in the container layer. The
  handler restarts the container under `COPY_ALWAYS` (default, `all.yml:43`) and recreates it when image, env or volumes
  differ, or under `COPY_ONCE` (`module_utils/kolla_docker_worker.py:341-363`). Only this start script writes the hash
  file (`:6,258`), so a new container starts without one. `collectstatic` and `compress` therefore run on the first
  start after a recreate (new image, plugin flag change, `COPY_ONCE`) or after a settings change, and not on a plain
  restart with unchanged settings and plugin flags. NOT AVAILABLE: how long they take. See
  [Kolla images §5](../../concepts/kolla-images.md#5-per-image-start-behaviour).
- Horizon config is independent of host count except for the memcached list.

---

## 5. HEAT

### 5.1 Play

```yaml
# ansible/site.yml:724-738
- name: Apply role heat
  gather_facts: false
  hosts: [heat-api, heat-api-cfn, heat-engine, '&enable_heat_True']
  serial: '{{ kolla_serial|default("0") }}'
  max_fail_percentage: '{{ heat_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}'
  roles: [{ role: heat, tags: heat }]
```
- LB include: `site.yml:183-187`. `enable_heat: "{{ enable_openstack_core | bool }}"` (`all.yml:772`).

### 5.2 `heat_services` (`ansible/roles/heat/defaults/main.yml:2-53`)

In 2024.1 the dict is at `ansible/roles/heat/defaults/main.yml:2-58`.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| heat-api | `heat_api` | heat-api | true | Apache/mod_wsgi on 8004, HAProxy internal and external (:11-26) |
| heat-api-cfn | `heat_api_cfn` | heat-api-cfn | true | Apache/mod_wsgi on 8000, HAProxy internal and external (:35-50) |
| heat-engine | `heat_engine` | heat-engine | true | No haproxy, not privileged. Volumes are config, localtime, timezone, dev-mode source and logs, plus `/dev/shm` when `om_enable_queue_manager` (new in 2024.1) (:162-168). |

### 5.3 Task flow

| action | flow |
|---|---|
| deploy / reconfigure | `register.yml` → `config.yml` → `check-containers.yml` → (clone) → `bootstrap.yml` → flush (`tasks/deploy.yml:1-15`) |
| upgrade | `config.yml` → `check-containers.yml` → `bootstrap_service.yml` (db sync with new image while the old engine and APIs still run) → flush, which restarts **all** heat-api, heat-api-cfn and heat-engine containers together (`tasks/upgrade.yml:1-9`). No `register.yml`. |
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

The wsgi template sets no `python-path`; both `WSGIScriptAlias` and the `<Directory>` block use
`binary_path = /var/lib/kolla/venv/bin` (`templates/wsgi-heat-api.conf.j2:2,18,34`), as placement does with its
`wsgi_directory` (`roles/placement/templates/placement-api-wsgi.conf.j2:2`). Still holds in 2024.1.

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
  `heat_domain_admin_password` (`etc/kolla/passwords.yml:108`) is therefore **not** pushed to Keystone, while
  `heat.conf` gets the new value (`templates/heat.conf.j2:11-12`). NOT AVAILABLE: whether stack-domain operations then
  fail authentication. The check looks only at the domain name, so if a run fails partway and leaves the domain without
  the user or its role, no later run repairs it. With Docker, the container is removed on exit, after a failure too
  (`module_utils/kolla_docker_worker.py:405-413`), so the passwords do not linger in `docker inspect`. But `kolla_start`
  runs with xtrace: when the bootstrap creates the domain, the `openstack user create … --password` line goes to stderr
  with `HEAT_DOMAIN_ADMIN_PASSWORD` expanded. The module returns that stderr in the task result
  (`module_utils/kolla_docker_worker.py:400-404`), which Ansible prints on failure or with `-v` (ansible-core 2.16.20
  `lib/ansible/plugins/callback/default.py:50-71,104-105`, `lib/ansible/plugins/callback/__init__.py:200-202`), and the
  task sets no `no_log` (kolla `docker/base/start.sh:6`, `docker/heat/heat-api/extend_start.sh:12`;
  [Kolla images §2.2](../../concepts/kolla-images.md#22-kolla_start-step-by-step)).
- Keystone: services `heat/orchestration` (`/v1/%(tenant_id)s`) and `heat-cfn/cloudformation` (`/v1`), each with 2
  endpoints (internal, public); user `heat`; roles `heat_stack_owner` and `heat_stack_user`; **`heat_stack_owner`
  granted to the cloud admin user in the admin project** (`defaults/main.yml:178-184,218-245`;
  `tasks/register.yml:2-9`). This runs on deploy/reconfigure, not on upgrade.

### 5.7 Dependencies (`templates/heat.conf.j2`)

- **Public endpoints reached from inside VMs:** `heat_metadata_server_url` and `heat_waitcondition_server_url` use
  `heat_cfn_public_base_endpoint` (:6-7), i.e. **`public_protocol`, `heat_cfn_external_fqdn` and
  `heat_api_cfn_public_port`** (`defaults/main.yml:181`; the port follows the single external frontend option,
  `all.yml:419`). `server_keystone_endpoint_type = public` (:23). Instances that use wait conditions or software
  deployments must be able to reach the **external** VIP on that port and the public keystone endpoint.
- **All other services:** `[clients] endpoint_type = internalURL` (:105-107). heat-engine calls nova, neutron, cinder,
  glance, swift, etc. through their internal catalog endpoints. The real dependency set is whatever the users' templates
  use.
- Keystone: `keystone_authtoken` (:31-46), plus `[trustee]` with the heat service user (:55-60), plus `[ec2authtoken]`
  (:62-63). `stack_domain_admin` = `heat_domain_admin` / `heat_domain_admin_password` (:11-13).
- MariaDB (:25-29); RabbitMQ RPC (:19), notifications (ceilometer only, otherwise `driver = noop`; :65-72,
  `defaults/main.yml:209-213`) and `[oslo_messaging_rabbit]` with quorum queues by default (:74-98); memcached for
  authtoken and `[cache]` (:44-52). New in 2024.1: with the queue manager, an `[oslo_concurrency] lock_path` (:120-123).
- `num_engine_workers = heat_engine_workers` = `openstack_service_workers` (≤5) per engine host (:15-17;
  `defaults/main.yml:196`).

### 5.8 Operational notes

- **heat-engine restarts with stacks in progress:** Docker sends SIGTERM, then SIGKILL if heat-engine is still running
  after 60 s (`module_utils/kolla_systemd_worker.py:32`; `group_vars/all.yml:139,151`;
  [§0](#0-cross-cutting-facts-apply-to-all-five-roles)). NOT AVAILABLE (upstream heat): how that compares with the
  duration of long resource creates; whether stacks that a killed engine owned stay `*_IN_PROGRESS` until some engine
  starts again; whether heat-engine's `reset_stack_status` then marks them `FAILED` ("Engine went down during stack …");
  and whether users must then run `stack update` or a check/resume.
- With serial 0, **every heat-engine restarts in the same handler flush** on any heat.conf change. A memcached or rabbit
  membership change, a password rotation, an `openstack_service_workers` change, or the first 2024.1 run of a cloud that
  kept classic queues ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)) is enough. Every in-progress stack in the
  cloud is therefore affected, not just a fraction.
- On upgrade the db sync runs while old engines are still active, and all engines restart together after it.
- Heat does not touch compute hosts. Its dependency on instance reachability to the external VIP (above) is the main
  network coupling.

---

## 6. Summary matrix: what `reconfigure` does per role

| role | keystone register | DB create/grant | bootstrap container (schema sync) on reconfigure | extra side effects on reconfigure | restarts (serial 0) |
|---|---|---|---|---|---|
| glance | yes | yes | **yes** (`KOLLA_BOOTSTRAP` on `glance_api_hosts[0]`) | **toggles GLOBAL `log_bin_trust_function_creators` 1→0** (unless `use_preconfigured_databases`); no sanity image in 2024.1 | glance-api (and tls-proxy) on `glance_api_hosts` only (1 host with the file backend) |
| placement | yes | yes | **yes** (also runs online data migrations) | – | all placement-api |
| cinder | yes | yes | **yes** | – (no sanity volume in 2024.1) | api, scheduler, **volume, backup on all storage hosts** at once if their config changed (the first 2024.1 run changes cinder-volume through `hostnqn`) |
| horizon | **no** | only if `horizon_backend_database` (default `false`) | only if `horizon_backend_database` | env-driven recreate when plugin flags change | all horizon |
| heat | yes (also roles and a grant to admin) | yes | **yes** (with admin creds in env) | – | api, api-cfn, **all engines** |

The separate online-data-migration container (`KOLLA_OSM`) runs **only on `upgrade`**, for placement
(`roles/placement/tasks/upgrade.yml:16-34`) and cinder (`roles/cinder/tasks/upgrade.yml:25-43`). Glance's
expand/migrate/contract runs only in the rolling path. A reconfigure with a bumped image tag therefore runs cinder's
`db sync` without its OSM step (kolla `docker/cinder/cinder-api/extend_start.sh:6-14`), while placement's bootstrap
container runs both `db sync` and `db online_data_migrations` (kolla
`docker/placement/placement-api/extend_start.sh:5-9`). A reconfigure also skips cinder's second "remove RPC version pin"
restart, which only `upgrade.yml:23` runs. Whether this leaves cinder in a partially upgraded state is NOT AVAILABLE.
See [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run).

## 7. Things that scale with host count

- memcached and rabbit host lists in every config ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)). Any membership
  change rewrites the config of all 5 services and restarts every container of every service.
- `glance_num_retries = len(groups['glance-api'])` (`roles/cinder/templates/cinder.conf.j2:20`).
- HAProxy backend lists: glance uses `glance_api_hosts` (`roles/glance/defaults/main.yml:86-87`); the others use
  `groups[host_group]` (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:101`).
- Placement and cinder credentials are embedded in nova-compute config on **every compute**. Password rotation therefore
  needs a reconfigure of the whole compute fleet ([§2.8](#28-operational-notes-and-the-relation-to-nova),
  [§3.7](#37-dependencies-templatescinderconfj2)).
- `run_once` tasks repeat per batch when `ANSIBLE_SERIAL` is set ([§0](#0-cross-cutting-facts-apply-to-all-five-roles)).

## 8. NOT AVAILABLE list

1. NOT AVAILABLE: whether an existing glance file-store image stays readable after `enable_swift: yes`,
   `glance_backend_ceph: yes` or `glance_backend_s3: yes` is applied by reconfigure.
2. Answered from code: Glance rolling upgrade with `ANSIBLE_SERIAL=1` runs the contract at the end of batch 1, before
   later batches are upgraded ([§1.8](#18-operational-notes) note 4;
   [§0](#0-cross-cutting-facts-apply-to-all-five-roles) run_once + serial;
   `roles/glance/tasks/rolling_upgrade.yml:80-102`).
3. NOT AVAILABLE: Glance-api start time with a large NFS `glance_file_datadir_volume` (recursive chown,
   `glance-api.json.j2:47-52`).
4. NOT AVAILABLE: whether the glance cinder store works with `cinder_catalog_info = volume:cinder:internalURL` and no
   `[cinder]` store section.
5. NOT AVAILABLE: whether cinder-backup works with default `cinder_backup_driver=ceph` and `cinder_backend_ceph=no`
   (kolla-ansible gives it no ceph config, [§3.8](#38-operational-notes) oddity 5).
6. NOT AVAILABLE: whether the volumes owned by one of several RBD cinder-volume nodes (`host`) can still be managed
   while that node is down, and what state an in-flight create-from-image is in after a cinder-volume restart.
7. Cinder RPC pinning after `kolla-ansible upgrade` (is a second restart needed?): answered from code for 2024.1: the
   role does a second restart of every cinder service after the upgrade flush and a 30 s pause, to remove the RPC
   version pin (`roles/cinder/tasks/upgrade.yml:20-23`, `tasks/reload.yml:2-10`, `handlers/main.yml:70-88`;
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
12. New in 2024.1, NOT AVAILABLE: how Horizon loads the `_9998`/`_9999` fragments of `local_settings.d` on top of the
    image's base `local_settings.py` ([§4.4](#44-config-files-ansibleroleshorizontasksconfigyml)), and which component
    creates the Keystone `service` role that the cinder role now only grants ([§3.6](#36-bootstrap)).

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
