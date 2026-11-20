---
title: Fact sheet A
description: "Fact sheet for the loadbalancer, haproxy-config, memcached, OVN, ovs-dpdk and service-cert-copy roles and the certificates playbook, 2024.1."
tags: [haproxy, keepalived, memcached, chrony, ovn, handlers, tags, serial]
---

# Fact sheet A

Scope: roles `haproxy` (in 2024.1, as in 2023.1, the `loadbalancer` role: haproxy, keepalived, proxysql, new
`haproxy_ssh`, and the per-service `loadbalancer.yml` fan-out), `haproxy-config`, `memcached`, `chrony` (gone since
2023.1), `ovn` (the `ovn-controller` and `ovn-db` roles), `ovs-dpdk`, `service-cert-copy`, and the `certificates.yml`
playbook/role.

Sources: kolla-ansible tag `2024.1-eom` (commit `890396f`), kolla `2024.1-eom` (commit `ed7a36a`). Paths that start
with `ansible/`, `tools/`, `kolla_ansible/`, `releasenotes/` or `doc/` are relative to the kolla-ansible repository
root; other kolla-ansible paths are relative to `ansible/`. Supported Ansible: ansible-core 2.15 to 2.16
(`tools/kolla-ansible:10-11`); this sheet cites ansible-core 2.16.20, the only version read (2.15 is NOT AVAILABLE).

How the evidence was gathered:
- **Code reading.** Every claim cites `path:line` in the 2024.1 trees.
- **Ansible semantics.** Tag inheritance, handler order and serial batches cite the ansible-core 2.16.20 source as
  ansible-core 2.16.20 `lib/ansible/<path>:N`. Ansible's own parse of `site.yml` is in
  [list-tags-site.txt](../listings/list-tags-site.txt).
- **Labels.** A claim with a `path:line` citation is a FACT read from the sources. `NOT AVAILABLE` marks what the
  sources do not establish, for example timings, runtime outcomes and anything about Podman on a real host.

> [!NOTE]
> **Key answers**
>
> - **Changed in 2024.1, OVS-DPDK:** the notify name mismatch of 2023.1 is fixed, so every `ovsdpdk-db` restart now
>   reaches `Wait for dpdk tunnel ip`, a `wait_for` with a host and no port, which sleeps the full 300 s on every DPDK
>   host of the batch (`roles/ovs-dpdk/handlers/main.yml:16-22, :88-92`; ansible-core 2.16.20
>   `lib/ansible/modules/wait_for.py:541-542`)
> ([6.5](#65-handlers-ansiblerolesovs-dpdkhandlersmainyml-in-definition-order)).
> - **Changed in 2024.1, load balancer:** new `haproxy_ssh` container (only with `enable_letsencrypt`), PEM files moved
>   to `/etc/haproxy/certificates/` on a named volume that every haproxy container now mounts, an optional single
>   external frontend, a `listen metrics` block in `haproxy.cfg`, and an upgrade step that removes
>   `prometheus_haproxy_exporter` (`roles/loadbalancer/defaults/main.yml:29-36, :121`,
>   `roles/loadbalancer/tasks/upgrade.yml:4-19`) ([1.2](#12-haproxy_services-ussuri-now-loadbalancer_services),
>   [1.4](#14-config-files-generated-ansibleroleshaproxytasksconfigyml)).
> - **Still holds:** a haproxy-relevant change is a staged stop/start of haproxy (backups first, then the VIP holder),
>   never a reload by Kolla-Ansible; stale `services.d` files are never removed; the OVN DB cluster and every
>   `ovn_controller` restart together under the default serial; `ovs-dpdkctl.sh install`/`bind_nics` run on every
>   deploy, reconfigure, upgrade and genconfig; certificates are never renewed
>   ([9](#9-cross-cutting-summary-restart-triggers-and-blast-radius)).
> - **New `max_fail_percentage` on every play** in scope, default 100: with 100 it never stops a play early (see
>   common mechanics).

Common mechanics that apply to every role below (all verified in code):
- **All containers use host networking.** The container module is now `kolla_container`; its Docker worker always
  sets `'network_mode': 'host'` (`module_utils/kolla_docker_worker.py:277-279`), and the new Podman worker does too
  (`module_utils/kolla_podman_worker.py:77`). "net=host" is therefore never a role flag. `kolla_container_engine`
  defaults to `docker` (`ansible/group_vars/all.yml:92`); this sheet follows the Docker path, and how Podman behaves
  on a host is NOT AVAILABLE.
- **A config-only change means a full stop+start.** `config_strategy: "COPY_ALWAYS"` (`ansible/group_vars/all.yml:43`)
  is passed as `KOLLA_CONFIG_STRATEGY` in `docker_common_options` (`ansible/group_vars/all.yml:142-153`). With
  COPY_ALWAYS and no parameter drift, `recreate_or_restart_container` calls `restart_container`
  (`module_utils/kolla_docker_worker.py:341-363`). **Still holds in 2024.1:** for a container with a systemd unit
  (every container except one-shot ones) that is a systemd `RestartUnit` of `kolla-<name>-container.service`, after the
  unit file is rewritten when it differs (`module_utils/kolla_docker_worker.py:439-459`,
  `module_utils/kolla_systemd_worker.py:71,106-113,172-185`). The unit's `ExecStop` is now
  `/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:32`), and
  `graceful_timeout` keeps the `common_options` value, `docker_graceful_timeout: 60` (`library/kolla_container.py:313`,
  `:361-393`; `ansible/group_vars/all.yml:139,151`) ([R24](../../risk/risk-register.md#r24)).
- **Changed in 2024.1, unit text:** the unit template changed, and `compare_container` compares the whole unit text
  (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_systemd_worker.py:154-167`). The first 2024.1
  check of a container whose unit 2023.1 wrote reports drift, and the restart handler runs
  ([F16](../findings.md#f16)). This applies to every container of this sheet that no 2024.1 run has recreated or
  restarted yet.
- **There is no "reload" path in the roles in scope.** The haproxy image still ships a reload helper,
  `kolla_ensure_haproxy_latest_config` (kolla `docker/haproxy/haproxy/Dockerfile.j2:17,21`,
  `docker/haproxy/haproxy/ensure_latest_config.sh:5-14`), but kolla-ansible 2024.1 never calls it (grep finds no
  caller). The helper would not reload haproxy here anyway: it signals `haproxy-systemd-wrapper` (`:11`), which
  `haproxy_run.sh` does not start (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38-40`). **New in 2024.1:**
  with `enable_letsencrypt`, a renewed certificate is loaded into the running haproxy through its admin socket
  (`set ssl cert`, `commit ssl cert`) by the `haproxy_ssh` image's `update-haproxy-cert`, called over SSH by the lego
  container (kolla `docker/haproxy/haproxy-ssh/update-haproxy-cert.sh:23,50,123-125`,
  `docker/letsencrypt/letsencrypt-lego/sync-and-update-certificate.sh:83-89`). That path is outside the
  Kolla-Ansible handlers.
- **`kolla_serial` is only set for two actions.** The CLI passes it only for `upgrade` and `reconfigure`
  (`tools/kolla-ansible:522,531`), from `ANSIBLE_SERIAL`, which defaults to `0` = all hosts at once
  (`tools/kolla-ansible:296`).
- **New in 2024.1, `max_fail_percentage` on every play.** Each play in scope sets
  `max_fail_percentage: {{ <play>_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}`
  (e.g. `ansible/site.yml:111-114`). It counts the failures of the current batch only: `PlaybookExecutor` runs
  `TaskQueueManager.run()` once per batch (ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:184-190`)
  and `run()` clears `_failed_hosts` (`lib/ansible/executor/task_queue_manager.py:330-338`); with 100 it never stops a
  play early.
- **Handlers fire in definition order across all hosts of the batch in lockstep** (linear strategy).
  - With the default serial 0, a handler restarts that container on **every host of the play at the same time**
    (unless the handler itself selects hosts, as the loadbalancer handlers do, section 1.5).
  - In ansible-core 2.16 a notification is first saved per host by name (ansible-core 2.16.20
    `lib/ansible/plugins/strategy/__init__.py:656-676`, `lib/ansible/executor/play_iterator.py:650-654`) and
    resolved to handlers at the flush (`strategy/__init__.py:952-962`). A name reaches the handler of that exact name
    and every handler that `listen`s to it (`strategy/__init__.py:511-567`). At a flush, every host walks the play's
    handler list in definition order and runs the handlers it was notified for (`play_iterator.py:200,426-445`); the
    linear strategy keeps the hosts on the same handler (`lib/ansible/plugins/strategy/linear.py:50-93`). A notify sent
    by a handler while handlers run is applied at once (`strategy/__init__.py:664-669`), so a handler defined later
    and notified that way runs in the same flush.
- **Handlers are not tag-filtered in ansible-core 2.16.**
  - Tags filter only the play's compiled task blocks and the blocks of non-handler includes (ansible-core 2.16.20
    `lib/ansible/executor/play_iterator.py:189-193`, `lib/ansible/plugins/strategy/linear.py:258-273`). The handler
    list is copied unfiltered (`play_iterator.py:200`) and handler selection has no tag check
    (`play_iterator.py:426-445`). So under `-t <service>` the handlers listening to `Restart haproxy container` still
    run, although they only carry the inherited play tags `haproxy`, `keepalived`, `loadbalancer`.

---

## 0. Plays in `ansible/site.yml` (summary table)

| Role | Play (lines) | Host pattern | Tags | serial |
|---|---|---|---|---|
| chrony | **none in 2024.1**: no chrony play, role, group or image ([Chrony](../../components/chrony.md)) | n/a | n/a | n/a |
| haproxy (+keepalived) | role `loadbalancer`, `site.yml:105-326` | `loadbalancer`, `&enable_loadbalancer_True` (107-109) | **play-level** `haproxy`, `keepalived`, `loadbalancer` (115-118) | `kolla_serial` (110) |
| haproxy-config | no play of its own. 39× `include_role <svc> tasks_from: loadbalancer` in a `block`, inside the loadbalancer play (`site.yml:122-326`) | loadbalancer hosts | per include: `<svc>`; nova/nova-cell: `[nova, nova-api]` / `[nova, nova-cell]` (252-265). Plus the inherited play tags | inherited |
| memcached | `site.yml:402-414` | `memcached`, `&enable_memcached_True` (404-406) | role-level `[memcache, memcached]` (413-414) | `kolla_serial` (407) |
| ovs-dpdk | `site.yml:626-639` | `openvswitch`, `&enable_openvswitch_True_enable_ovs_dpdk_True` (628-630) | role-level `ovs-dpdk` (637-639) | `kolla_serial` (631) |
| ovn | two plays: `ovn-controller` `site.yml:641-653`, `ovn-db` `site.yml:655-669` | `ovn-controller` / `ovn-nb-db`, `ovn-northd`, `ovn-sb-db`; each `&enable_ovn_True` | role-level `[ovn, ovn-controller]` (652-653) / `[ovn, ovn-db]` (668-669) | `kolla_serial` (646, 662) |
| service-cert-copy | no play. Imported from `<role>/tasks/copy-certs.yml` (38 roles, including `loadbalancer`) | caller's | caller's | caller's |
| certificates | separate playbook `ansible/certificates.yml:1-11` (`kolla-ansible certificates`, `tools/kolla-ansible:546-549`) | `localhost` | none | none |

- **Every play in scope also sets `max_fail_percentage`** (default 100), e.g. `site.yml:111-114`, `:408-411`,
  `:632-635`, `:647-650`, `:663-666` (see common mechanics). The certificates play does not
  (`ansible/certificates.yml:8-11`).
- **Pattern groups.** The `enable_*` pattern groups are created by `group_by` in `site.yml:20-75`:
  - loadbalancer line 48 (`enable_loadbalancer` = haproxy or keepalived or proxysql enabled, `group_vars/all.yml:725`),
    memcached 53, openvswitch/ovs_dpdk 61, ovn 62. There is no chrony entry. New: letsencrypt 47.
- **Play order matters.** It runs common (88) → loadbalancer (105) → **letsencrypt (328, new)** → … `mariadb.yml` (400)
  → memcached (402) → … `nova.yml` (609) → openvswitch (611) → ovs-dpdk (626) → ovn-controller (641) → ovn-db (655) →
  neutron (671).
- **Common dependency.** **Still holds in 2024.1:** no role in scope has a `meta/` directory, so none has a `common`
  dependency (`roles/{loadbalancer,memcached,ovn-controller,ovn-db,ovs-dpdk}` have no `meta/`). `common` is its own
  play, tagged `common` only (`site.yml:88-103`), and `roles/common/tasks/main.yml:2` has no guard.
- **service-cert-copy count.** 40 roles have a `copy-certs.yml`; 38 of them import `service-cert-copy`. `etcd` and
  `rabbitmq` copy their files with their own tasks (e.g. `roles/etcd/tasks/copy-certs.yml:2-12`).

---

## 1. `haproxy` role (haproxy + keepalived)

**Still holds in 2024.1:** this role is `loadbalancer` (`ansible/roles/loadbalancer/`). It runs `haproxy`, `keepalived`
and, with `enable_proxysql` (default `no`, `group_vars/all.yml:839`), `proxysql`. **New in 2024.1:** with
`enable_letsencrypt` (default `no`, `group_vars/all.yml:796`) it also runs `haproxy_ssh`. ProxySQL and `haproxy_ssh`
are described here only where they change the haproxy/keepalived behaviour.

### 1.1 Play

- **Play:** `site.yml:105-326`. Hosts `loadbalancer` ∩ `enable_loadbalancer_True`, `serial: kolla_serial`, new
  `max_fail_percentage` (111-114), play-level `tags: [haproxy, keepalived, loadbalancer]`.
- **Role entry:** `- { role: loadbalancer }` (120), with no `when`.
- **The loadbalancer block.** The play then has a `tasks:` block of 39 `include_role` statements (122-323; 44 in
  2023.1) guarded by (324-326):
  ```yaml
  when:
    - enable_haproxy | bool
    - kolla_action in ['deploy', 'reconfigure', 'upgrade', 'config']
  ```
  - **Changed in 2024.1:** the freezer, murano, sahara, senlin, solum and vitrage includes are gone, a `letsencrypt`
    include is new (`site.yml:208-212`), and the rabbitmq include is `when: enable_rabbitmq | bool` only (288).
- **Role entry point.** `roles/loadbalancer/tasks/main.yml:2-3` is
  `include_tasks: "{{ kolla_action }}.yml"` with `when: inventory_hostname in groups['loadbalancer']`.
- **Default inventory.** `[loadbalancer:children] network` (`ansible/inventory/multinode:84-85`). There is no
  `haproxy` group. New: `[letsencrypt:children] loadbalancer` (`ansible/inventory/multinode:192-193`).

### 1.2 `haproxy_services` (Ussuri; now `loadbalancer_services`)

In 2024.1 the dict is `loadbalancer_services` (`roles/loadbalancer/defaults/main.yml:2-36`).

| key | container | group | enabled | privileged | notable volumes |
|---|---|---|---|---|---|
| haproxy | `haproxy` | loadbalancer | `true` | **True** | `/etc/kolla/haproxy/:/var/lib/kolla/config_files/:ro`, named volume `haproxy_socket:/var/lib/kolla/haproxy/`, **new** named volume `letsencrypt_certificates:/etc/haproxy/certificates` (116-121) |
| proxysql | `proxysql` | loadbalancer | `enable_proxysql` | False | `kolla_logs`, `proxysql:/var/lib/proxysql/`, `proxysql_socket:/var/lib/kolla/proxysql/` (123-129) |
| keepalived | `keepalived` | loadbalancer | `enable_keepalived` | **True** | `/lib/modules:/lib/modules:ro`, `haproxy_socket` when `enable_haproxy`, `proxysql_socket` when `enable_proxysql` (130-136) |
| haproxy-ssh (**new**) | `haproxy_ssh` | loadbalancer | `enable_letsencrypt` | not set (False) | `haproxy_socket`, and with letsencrypt `letsencrypt:/etc/letsencrypt` and `letsencrypt_certificates:/etc/haproxy/certificates` (137-143); no `_extra_volumes` |

- **Keepalived default.** `enable_keepalived: "{{ enable_haproxy | bool }}"` (`ansible/group_vars/all.yml:724`) and
  `enable_haproxy: "yes"` (723).
- **Changed in 2024.1, haproxy volumes.** The `letsencrypt_certificates` volume is always mounted, with or without
  Let's Encrypt (`roles/loadbalancer/defaults/main.yml:121`), so the haproxy container definition differs from a
  2023.1 one.
- **Shared socket volume.** The `haproxy_socket` volume is shared between haproxy, keepalived and, new, `haproxy_ssh`.
  The haproxy stats socket is `stats socket /var/lib/kolla/haproxy/haproxy.sock`, with `level admin` when
  `haproxy_socket_level_admin` (`roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:13`), which now follows
  `enable_letsencrypt` (`roles/loadbalancer/defaults/main.yml:182`).
  - **Still holds in 2024.1:** the keepalived health check is rendered by kolla-ansible. `config.yml` writes one
    `check_alive_<service>.sh` per enabled haproxy/proxysql service into `/etc/kolla/keepalived/checks/`
    (`roles/loadbalancer/tasks/config.yml:93-111`) and removes those of disabled services (74-91); both tasks now skip
    `haproxy-ssh` (86, 107) and run only with `keepalived_track_script_enabled` (83, 103). keepalived's `config.json`
    copies that directory to `/checks` (`templates/keepalived/keepalived.json.j2:10-15`). The haproxy check runs
    `echo "show info" | socat unix-connect:/var/lib/kolla/haproxy/haproxy.sock stdio`
    (`templates/keepalived/check_alive_haproxy.sh.j2:6`); the proxysql check asks the ProxySQL admin socket
    (`check_alive_proxysql.sh.j2:6`). The image's `/check_alive.sh` runs every file under `/checks` and fails if one
    fails (kolla `docker/keepalived/check_alive.sh:9-32`, baked in by kolla `docker/keepalived/Dockerfile.j2:21,25`).
    **Changed in 2024.1:** the legacy single `socat` check at the end of that script is gone; the file ends at line 33.
- Haproxy, proxysql and `haproxy_ssh` have a container healthcheck (`roles/loadbalancer/defaults/main.yml:76-113`;
  haproxy: a `healthcheck_curl` of the monitor port on `api_interface_address`, 80; `haproxy_ssh`:
  `healthcheck_listen sshd`, 106). keepalived has none (21-28).
- No pid_mode or ipc_mode is set.

### 1.3 Task flow per `kolla_action`

| action | task files (in order) | notes |
|---|---|---|
| deploy | `config-host.yml` → `config.yml` → `check-containers.yml` (`roles/loadbalancer/tasks/deploy.yml:2-6`) | **No `flush_handlers`.** Comment `roles/loadbalancer/tasks/deploy.yml:8-11`: "haproxy role handlers should not be flushed early. site.yml handles all haproxy things in a dedicated play… See bug 1875228". The per-service loadbalancer includes then run (site.yml block) and the handlers flush once at the end of the play. |
| reconfigure | `roles/loadbalancer/tasks/reconfigure.yml:2` → `import_tasks: deploy.yml` | identical to deploy |
| upgrade | **Changed in 2024.1:** first `stop_and_remove_container` of `prometheus_haproxy_exporter` and removal of `/etc/kolla/prometheus-haproxy-exporter` on loadbalancer hosts (`roles/loadbalancer/tasks/upgrade.yml:4-19`), then `import_tasks: deploy.yml` (21) | otherwise identical to deploy; the staged handlers (1.5) apply image changes. See 1.8 (F). |
| deploy-containers | `check-containers.yml` (`roles/loadbalancer/tasks/deploy-containers.yml:2`) | the loadbalancer block is **not** run (`site.yml:326`) |
| pull | `service-images-pull` (`roles/loadbalancer/tasks/pull.yml:2-3`): pulls the images of `loadbalancer_services` (`project_name: "loadbalancer"`, `roles/loadbalancer/vars/main.yml:2`; `lookup('vars', … + '_services')`, `ansible/roles/service-images-pull/tasks/main.yml:14`) | `haproxy_ssh` only where enabled (`select_services_enabled_and_mapped_to_host`, same line) |
| stop | `service-stop` with `loadbalancer_services` (`roles/loadbalancer/tasks/stop.yml:2-6`) | stops **haproxy, keepalived (and proxysql, haproxy_ssh) on all loadbalancer hosts**, so no API frontend runs; whether the VIP is then released is NOT AVAILABLE. `skip_stop_containers` can exclude them (`ansible/roles/service-stop/tasks/main.yml:10-11`). |
| precheck | `precheck.yml` (751 lines, 60 named top-level tasks) | `service-precheck` group validation (2-6). Container facts (8-17) and grouping by running container (19-44). Whole-batch detection for the VIP checks (46-55, which skip when `--limit`/serial does not cover all loadbalancer hosts). Cert existence on localhost (57-99), **now skipped with `enable_letsencrypt`**. External VIP iface present/active (101-113). VIPs not pingable (115-128, only when keepalived runs nowhere). Free ports for stats, monitor and ProxySQL admin (130-190). VIP in the same subnet as `api_interface` (192-206). `show stat` through the socket (208-218). Then one "free port" check per service on the VIP (from 220; the checks of the removed services are gone), skipped when that frontend already exists in `haproxy_stat`, and firewalld checks at the end when `enable_external_api_firewalld` (732-751). |
| check | `check.yml` is empty | |
| config (genconfig) | `config.yml` only (no `config-host.yml`). The loadbalancer block **does** run (`'config'` is in the list, `site.yml:326`). | Every restart handler has `when: kolla_action != "config"` (`roles/loadbalancer/handlers/main.yml:16-17,29-30,44-45`, …, `:344-345`), so nothing restarts. The next `deploy-containers` detects drift through `kolla_set_configs --check` and restarts, for drift in `config_files` entries only ([F14](../findings.md#f14)). |

**Key tasks:**
- **`roles/loadbalancer/tasks/config-host.yml:3-25`.** These run on deploy, reconfigure and upgrade:
  - **Changed in 2024.1:** the sysctl writes go through the new `sysctl` role (`include_role`, 8-18), only when
    `set_sysctl` (default `yes`, `group_vars/all.yml:703`): `net.ipv6.ip_nonlocal_bind=1`,
    `net.ipv4.ip_nonlocal_bind=1`, `net.ipv4.tcp_retries2=<haproxy_host_ipv4_tcp_retries2>`,
    `net.unix.max_dgram_qlen=128` (12-16), written to `kolla_sysctl_conf_path` (`/etc/sysctl.conf`,
    `group_vars/all.yml:706`) by `roles/sysctl/tasks/main.yml:7-20`.
  - Same values and logic as 2023.1: `KOLLA_UNSET` (the default, `roles/loadbalancer/defaults/main.yml:179`) means
    `state: absent`; `KOLLA_SKIP` skips the item; IPv6 keys are skipped when IPv6 is disabled
    (`roles/sysctl/tasks/main.yml:10-20`). The IPv6 check now runs twice: in `config-host.yml:3-6` and again in the
    sysctl role (`roles/sysctl/tasks/main.yml:2-5`).
  - Then `module-load` with `ip_vs` (20-25). This is loaded even when `enable_keepalived` is false, because it has no
    `when`.
- **`roles/loadbalancer/tasks/check-containers.yml:2-18`.** `compare_container` for each enabled service, notifying
  `"Restart {{ item.key }} container"`.

### 1.4 Config files generated (`ansible/roles/haproxy/tasks/config.yml`)

In 2024.1: `roles/loadbalancer/tasks/config.yml` (19 entries: 18 named tasks and the `copy-certs.yml` include).

| dest (host) | source / override order | notifies |
|---|---|---|
| `/etc/kolla/{haproxy,proxysql,keepalived,haproxy-ssh}/` dirs (2-13), `/etc/kolla/haproxy/services.d/` (15-27), `proxysql/{users,rules}` (29-44), `keepalived/checks/` (46-58) | n/a | none |
| removes `/etc/kolla/haproxy/services.d/mariadb.cfg` when ProxySQL is enabled (60-72) | n/a | Restart haproxy container |
| `/etc/kolla/keepalived/checks/check_alive_<svc>.sh` (74-111) | removed for disabled services, templated for enabled ones; both only with `keepalived_track_script_enabled` | Restart keepalived container |
| `/etc/kolla/<svc>/config.json` (113-124) | `templates/<svc>/<svc>.json.j2`, including the new `haproxy-ssh/haproxy-ssh.json.j2` | `Restart <svc> container` |
| `/etc/kolla/haproxy/haproxy.cfg` (126-142) | first_found: `{{node_custom_config}}/haproxy/<inventory_hostname>/haproxy_main.cfg` → `{{node_custom_config}}/haproxy/haproxy_main.cfg` → `haproxy/haproxy_main.cfg.j2` | Restart haproxy container |
| `/etc/kolla/proxysql/proxysql.yaml` (144-160) | same pattern under `{{node_custom_config}}/proxysql/` | Restart proxysql container |
| **new:** `/etc/kolla/haproxy/services.d/external-frontend.cfg` (162-175) | `haproxy/haproxy_external_frontend.cfg.j2`, only when `haproxy_single_external_frontend` (default `false`, `group_vars/all.yml:931`) | Restart haproxy container |
| `/etc/kolla/haproxy/services.d/*.cfg` (177-191) | `with_fileglob: {{node_custom_config}}/haproxy/services.d/*.cfg` (operator custom frontends) | Restart haproxy container |
| `/etc/kolla/keepalived/keepalived.conf` (193-209) | first_found: `…/keepalived/<host>/keepalived.conf` → `…/keepalived/keepalived.conf` → `keepalived/keepalived.conf.j2` | Restart keepalived container |
| `/etc/kolla/haproxy/haproxy.pem` (211-228) | `copy` from `kolla_external_fqdn_cert` (`/etc/kolla/certificates/haproxy.pem`, `group_vars/all.yml:925`), when `kolla_enable_tls_external`, not `kolla_externally_managed_cert` and, **new**, not `enable_letsencrypt` | Restart haproxy container |
| `/etc/kolla/haproxy/haproxy-internal.pem` (230-247) | from `kolla_internal_fqdn_cert` (926), same conditions with `kolla_enable_tls_internal` | Restart haproxy container |
| `/etc/kolla/{haproxy,keepalived,proxysql,haproxy-ssh}/ca-certificates/` (249-251 → `copy-certs.yml:2-6` → `service-cert-copy`) | `{{kolla_certificates_dir}}/ca/`, only when `kolla_copy_ca_into_containers` | `Restart haproxy container` **and** `Restart keepalived container` (and the proxysql / haproxy-ssh topics when enabled; see section 7) |
| `/etc/kolla/haproxy/haproxy_run.sh` (253-269), `/etc/kolla/proxysql/proxysql_run.sh` (271-287) | first_found: `…/<svc>/<host>/<svc>_run.sh` → `…/<svc>/<svc>_run.sh` → template | Restart haproxy / proxysql container |
| **new:** `/etc/kolla/haproxy-ssh/{sshd_config,id_rsa.pub}` (289-304) | templates, mode 0600, only where `haproxy-ssh` is enabled | Restart haproxy-ssh container |
| `/etc/kolla/haproxy/services.d/<service-key>.cfg` | written by **haproxy-config** (section 2) from each service role's `loadbalancer.yml` | Restart haproxy container |
| **new:** `/etc/kolla/haproxy/external-frontend-map` | written by **haproxy-config** with `blockinfile`, one block per service key, only with `haproxy_single_external_frontend` (`roles/haproxy-config/tasks/main.yml:25-53`) | Restart haproxy container |

Inside the container:
- **haproxy.json.j2.** It copies `haproxy_run.sh`, `haproxy.cfg` and the whole `services.d/` directory
  (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:2-20`). **Changed in 2024.1:** the external-frontend map and
  `haproxy.pem` are listed only when `kolla_enable_tls_external` and not `enable_letsencrypt` (21-35), and
  `haproxy-internal.pem` only when `kolla_enable_tls_internal` and not `enable_letsencrypt` (36-44). The PEM files now
  go to `/etc/haproxy/certificates/`, owned by `haproxy` (31-32, 39-40), the mount point of the
  `letsencrypt_certificates` named volume (1.2).
  - Oddity (code fact): `external-frontend.cfg` is written whenever `haproxy_single_external_frontend` is on
    (`roles/loadbalancer/tasks/config.yml:162-175`) and reads `/etc/haproxy/external-frontend-map`
    (`templates/haproxy/haproxy_external_frontend.cfg.j2:11`), but the map is copied into the container only with
    external TLS and without Let's Encrypt (`haproxy.json.j2:21-28`). What haproxy does when the map file is absent is
    NOT AVAILABLE.
- **haproxy_run.sh.j2.** **New in 2024.1:** with TLS on, when a PEM file is missing in `/etc/haproxy/certificates/`,
  it first writes a one-day self-signed certificate there (3-36). Then it runs
  `haproxy -W -db -p /run/haproxy.pid -f /etc/haproxy/haproxy.cfg` plus one `-f` per file found by
  `find /etc/haproxy/services.d/ -mindepth 1` (38-40). That is *every* file, not only `*.cfg`.
  - It is started in master-worker mode (`-W`), which could do a SIGUSR2 reload, but Kolla never uses that.
- **haproxy_main.cfg.j2.**
  - **Changed in 2024.1:** `nbthread {{ haproxy_threads }}` replaces `nbproc`, with a fixed `cpu-map auto:1/all 0-63`
    when `haproxy_thread_cpu_map` is on and more than one thread is set (9-12; `defaults/main.yml:66-67`). The old
    names `haproxy_processes`/`haproxy_process_cpu_map` are no longer read.
  - `listen stats` is on `api_interface_address:haproxy_stats_port` (1984) (36-43; `group_vars/all.yml:406`).
  - **New:** `listen metrics` on `api_interface_address:prometheus_haproxy_exporter_port` (9101) with HAProxy's
    built-in `prometheus-exporter`, when `enable_prometheus_haproxy_exporter` (45-50), which defaults to
    `enable_haproxy` (`group_vars/all.yml:567, :1213`).
  - `frontend status` (monitor-uri) is on `api_interface_address:61313` and, when it differs, on `VIP:61313` (52-58).
  - `haproxy_monitor_port: "61313"` (`group_vars/all.yml:407`).
- **keepalived.conf.j2** (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2`), unchanged from 2023.1:
  - `vrrp_script check_alive { script "/check_alive.sh" interval 2 fall 2 rise 10 }` (1-8), only while
    `keepalived_track_script_enabled` (default True, `defaults/main.yml:187`).
  - `state BACKUP` + `nopreempt` (11-12).
  - **`priority {{ groups['loadbalancer'].index(inventory_hostname) + 1 }}`** (15).
  - Unicast peers are built from `groups['loadbalancer']` only with `keepalived_traffic_mode == 'unicast'` (17-29). The
    VIP(s) are at 30-35. `track_interface` for the external VIP (36-40). `auth_type PASS` (41-44). `track_script
    check_alive` (45-49).
  - `keepalived_virtual_router_id: "51"` (`group_vars/all.yml:224`). `keepalived_traffic_mode: "multicast"`
    (`roles/loadbalancer/defaults/main.yml:62`).

### 1.5 Handlers (`ansible/roles/haproxy/handlers/main.yml`). Definition order = run order (see common mechanics)

**Still holds in 2024.1:** the handlers are in `roles/loadbalancer/handlers/main.yml`; apart from the module name
(`kolla_container`) and the new last handler, the file is unchanged from 2023.1. The names that tasks notify
(`Restart haproxy container`, `Restart proxysql container`, `Restart keepalived container`) are not handlers of their
own: they are `listen` topics of a staged sequence. The comment at 2-6 states the intent: delay restarting the master
keepalived and haproxy, which control the VIP, until the backups work, and let the master close its connections
before dropping the VIP by stopping keepalived. In definition order:

1. **`Check IP addresses on the API interface`** (9-21): `ip -4|-6 -o addr show dev <api_interface>`, on every
   notified host. Listens to all three topics.
2. **`Group HA nodes by status`** (23-34): `group_by` into `kolla_ha_is_master_True` (the host's address list contains
   `kolla_internal_vip_address`) or `kolla_ha_is_master_False`. Listens to all three topics.
3. **`Stop backup keepalived container`** (36-49): backups only; topic `Restart keepalived container`.
4. **`Stop backup haproxy container`** (54-68): backups; topics haproxy and keepalived.
5. **`Stop backup proxysql container`** (70-88): backups; all three topics (`ignore_missing`).
6. **`Start backup haproxy container`** (90-113): `recreate_or_restart_container`; topics haproxy and keepalived;
   notifies `Wait for backup haproxy to start` (115-118: `wait_for api_interface_address:haproxy_monitor_port`).
7. **`Start backup proxysql container`** (120-147), when enabled; notifies `Wait for backup proxysql to start`
   (149-152).
8. **`Start backup keepalived container`** (154-175): topic keepalived; notifies `Wait for virtual IP to appear`.
9. **`Stop master haproxy container`** (179-193), **`Stop master proxysql container`** (195-208, topics proxysql and
   keepalived), **`Stop master keepalived container`** (210-222, topic keepalived only).
10. **`Start master haproxy container`** (224-247) → `Wait for master haproxy to start` (249-252);
    **`Start master proxysql container`** (254-277) → `Wait for master proxysql to start` (279-282);
    **`Start master keepalived container`** (284-305) → `Wait for virtual IP to appear`.
11. **`Wait for haproxy to listen on VIP`** (307-317) and **`Wait for proxysql to listen on VIP`** (319-329):
    `wait_for kolla_internal_vip_address:<port>`, both `listen: Wait for virtual IP to appear`.
12. **New in 2024.1: `Restart haproxy-ssh container`** (331-345): a plain handler, no `listen`, no backup/master split:
    it restarts `haproxy_ssh` on every notified host at once, after the sequence above.

Every stop/start handler has `when: kolla_action != "config"`. The `wait_for` handlers set no timeout, so the module
default applies (300 s, ansible-core 2.16.20 `lib/ansible/modules/wait_for.py:482`), and only prove that a port
listens; they say nothing about the backends.

Other properties:
- There is no `run_once`, `delegate_to` or serial logic inside the handlers. The backup/master split is the only
  ordering: all backups of the batch stop and start in the same handler step, then the master.
- **If no host of the batch holds the VIP** (e.g. `enable_keepalived: no` with an external load balancer, or the VIP
  is on no loadbalancer host), every host is grouped as a backup and all of them stop and start haproxy at once; the
  master handlers are skipped (`groups.kolla_ha_is_master_True is defined`, 189, 240).
- With `kolla_serial=1`, Ansible runs the whole play, handler flushes included, once per one-host batch (ansible-core
  2.16.20 `lib/ansible/executor/playbook_executor.py:181-190`, `:274-304`; flush points
  `lib/ansible/playbook/play.py:345-351`).
- No other role notifies these topics except through `haproxy-config`
  (`ansible/roles/haproxy-config/tasks/main.yml:22-23`,
  and the new single-frontend task, `:52-53`) and `proxysql-config`
  (`roles/proxysql-config/tasks/main.yml:10-11,21-22`),
  both imported by `loadbalancer-config`.

### 1.6 Bootstrap / DB / Keystone / RabbitMQ registration

None.

### 1.7 Dependencies

- **VIP-related variables.** `kolla_internal_vip_address`, `kolla_external_vip_address` (`group_vars/all.yml:48-50`),
  `haproxy_enable_external_vip` (919), `api_interface`, `kolla_external_vip_interface` (286-287).
- **TLS:** `kolla_enable_tls_{internal,external}` and the cert paths (922-926). These are produced by the
  `certificates` playbook (section 8), supplied by the operator or, new in 2024.1, by the `letsencrypt` role
  (`site.yml:328-340`).
- **Everything behind the VIP.** Every service's `loadbalancer.yml` (section 2) builds backend lists from
  `groups[<svc group>]` and `hostvars[host].ansible_facts.hostname`, so facts are needed for all backend hosts (handled
  by `ansible/gather-facts.yml`, including the `--limit` path at 28-62).
  - `database_address: "{{ kolla_internal_fqdn }}"` (`group_vars/all.yml:83`) and `kolla_internal_fqdn` = the VIP
    (49). So **all DB traffic goes through the load balancer** (haproxy, or ProxySQL when enabled).
- **chrony.** Not a dependency: 2024.1 has no chrony role (section 4).
- **Logging.** `syslog_server: "{{ api_interface_address }}"` (`roles/loadbalancer/defaults/main.yml:58`) and
  `syslog_udp_port` (fluentd) (`group_vars/all.yml:630`). This needs fluentd from the `common` play.

### 1.8 Operationally notable behaviour

- **(A) Any change means a full restart of haproxy on all loadbalancer nodes, never a reload by Kolla-Ansible.**
  - Every haproxy-relevant change goes to the `Restart haproxy container` topic. That includes a change in any one
    service's `services.d/<svc>.cfg`, the external-frontend map, a cert, haproxy.cfg or haproxy_run.sh.
  - **Still holds in 2024.1:** the restart is staged (1.5): `haproxy` stops and starts on all backups of the batch at
    once, the play waits for their monitor port, then it stops and starts on the VIP holder. Each stop is a systemd
    stop of the unit, i.e. `<engine> stop -t 60` ([R24](../../risk/risk-register.md#r24)). While the master's haproxy is
    stopped, every API, MariaDB (through the VIP, `group_vars/all.yml:83`), RabbitMQ management, etc. that reaches the
    VIP holder is not served there.
  - Exception, new in 2024.1: a Let's Encrypt renewal is loaded through the admin socket by the letsencrypt containers,
    without a Kolla-Ansible restart (common mechanics).
  - NOT AVAILABLE: how long the outage lasts per run, and whether established connections are cut. From the code:
    `haproxy_run.sh` does not `exec` haproxy (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38-40`), so
    dumb-init's child is bash, not haproxy ([Kolla images §2.6](../../concepts/kolla-images.md#26-signals-and-pid-1)).
    Whether haproxy itself gets the SIGTERM of the engine stop is NOT AVAILABLE; a container still running after 60 s
    is killed.
- **(B) Whether a haproxy restart causes VIP failover or a VIP outage is NOT AVAILABLE.**
  - keepalived tracks `check_alive` with `interval 2 fall 2 rise 10`
    (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:2-7`).
  - NOT AVAILABLE: whether keepalived goes to FAULT and drops the VIP while haproxy is stopped on the VIP holder, and
    how long the VIP is then absent. The backups are already restarted at that point (1.5). The "Wait for master
    haproxy" handler checks `api_interface_address`, not the VIP (`roles/loadbalancer/handlers/main.yml:249-252`).
  - `nopreempt` is set (`keepalived.conf.j2:12`). Which node holds the VIP afterwards is NOT AVAILABLE.
  - The check itself is known: `/check_alive.sh` runs `check_alive_haproxy.sh`, which asks the haproxy stats socket
    for `show info` (section 1.2), so it fails as soon as haproxy stops answering on the socket. The FAULT and `rise`
    timing is upstream keepalived behaviour. NOT AVAILABLE: the timing and keepalived's initial script state.
  - A keepalived change (`Restart keepalived container`) stops and starts keepalived on the backups, then stops
    haproxy, proxysql and keepalived on the VIP holder, which the handler comment describes as dropping the VIP
    (`handlers/main.yml:2-6, :210-222`). Where the VIP goes and for how long is NOT AVAILABLE.
- **(C) keepalived priority depends on inventory order.**
  - `priority = index in groups['loadbalancer'] + 1` (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`).
  - Inserting, removing or re-ordering a loadbalancer host changes `keepalived.conf` on every host after it in the
    list. In unicast mode it changes on all hosts (peer list, 20-27). Each changed host goes through the staged
    keepalived sequence of 1.5. Whether that moves or flaps the VIP is NOT AVAILABLE.
- **(D) Stale frontends are never removed.**
  - Nothing in the tree deletes files in `services.d`, except `mariadb.cfg` when ProxySQL is enabled
    (`roles/loadbalancer/tasks/config.yml:60-72`); `haproxy-config` only templates and adds map blocks
    (`roles/haproxy-config/tasks/main.yml:2-53`).
  - If a service is disabled (`enable_X: no`), its `include_role` is skipped (`when: enable_X`). The old
    `/etc/kolla/haproxy/services.d/X.cfg` stays and is loaded by `haproxy_run.sh` on the next restart.
  - The same is true for removed custom `node_custom_config/haproxy/services.d/*.cfg` files, for
    `external-frontend.cfg` after `haproxy_single_external_frontend` is turned off (its task is then skipped,
    `config.yml:170-173`), and for a disabled service's block in `external-frontend-map` (the `blockinfile` task runs
    only for enabled services, `roles/haproxy-config/tasks/main.yml:47-51`).
  - BUG/oddity (code fact).
- **(E) `-t haproxy` also runs `common` on haproxy hosts.** **No longer holds (since 2023.1, still in 2024.1).** No
  role has a `common` meta dependency and `common` is its own play, tagged `common` only (`site.yml:88-103`). Ansible's
  own parse lists no `common` tag in the loadbalancer play ([list-tags-site.txt](../listings/list-tags-site.txt),
  play #6). So `kolla-ansible -t haproxy reconfigure` does not touch fluentd, cron or kolla-toolbox.
- **(F) Upgrade "Stopping all slave keepalived containers".** **Does not exist in 2024.1** (gone since 2023.1).
  `roles/loadbalancer/tasks/upgrade.yml` now holds two other tasks, the removal of the `prometheus_haproxy_exporter`
  container and its configuration on every loadbalancer host (4-19), then imports `deploy.yml` (21). A keepalived
  image or configuration change is applied by the staged handlers (1.5).
  - The Ussuri **Likely BUG 1** stays gone: the stop handlers pass `ignore_missing: true`
    (`handlers/main.yml:41,59,75,184,201,216`), and the new exporter removal uses `stop_and_remove_container`, which
    does nothing when the container is absent (`module_utils/kolla_docker_worker.py:433-437`).
  - The Ussuri **Likely BUG 2** stays gone: the handlers read the addresses with `ip addr show dev {{ api_interface }}`
    instead of facts (`handlers/main.yml:9-15`), and the precheck converts the interface name:
    `ansible_facts[kolla_external_vip_interface | replace('-', '_')]` (`roles/loadbalancer/tasks/precheck.yml:108-113`).
- **(G) Things that run on every deploy, reconfigure and upgrade:**
  - The IPv6 check (twice), sysctl and modprobe (config-host and the `sysctl` role).
  - The 19 entries of `config.yml` (directories, checks, templates, copies).
  - 2× `compare_container` (one more with ProxySQL, one more with Let's Encrypt), each of which does an
    `<engine> exec kolla_set_configs --check`.
  - Plus up to 39 service includes, each importing `loadbalancer-config` → `haproxy-config` (one template task, the
    single-frontend `blockinfile` task and one firewalld task, `roles/haproxy-config/tasks/main.yml:2-71`) and, with
    ProxySQL, `proxysql-config`.
  - On upgrade, the exporter removal (two tasks).
  - The cost scales with the number of loadbalancer hosts, not with computes.
  - The `sysctl` task with `KOLLA_UNSET` *removes* any manual `net.ipv4.tcp_retries2` line from `/etc/sysctl.conf` on
    every run (`roles/loadbalancer/tasks/config-host.yml:15`, `roles/sysctl/tasks/main.yml:10-16`).
- **(H) Non-local bind is needed.**
  - `ip_nonlocal_bind=1` is set only when `set_sysctl` is true (`roles/loadbalancer/tasks/config-host.yml:13-14,17-18`).
    Backup nodes bind VIP addresses (`roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:55`; every frontend,
    `roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:50`; the single external frontend,
    `haproxy_external_frontend.cfg.j2:10`).
  - NOT AVAILABLE: whether haproxy starts on non-VIP nodes with `set_sysctl: no` and no manual sysctl.
- **(I) VRRP router id collisions.** `keepalived_virtual_router_id` defaults to `51` with multicast. Two Kolla clouds on
  the same L2 segment collide unless it is changed (`group_vars/all.yml:224`,
  `roles/loadbalancer/defaults/main.yml:62`).

### 1.9 What exactly happens in the haproxy play for `-t <service>` and `-t haproxy`

How the tags combine (the mechanics, ansible-core 2.16.20):
1. **Play tags.** They are inherited by everything statically in the play: the role tasks, the `block`, and each
   `include_role` statement. A loadbalancer role task ends up with tags `{haproxy, keepalived, loadbalancer}`. `tags`
   is an extending attribute that collects the parent, role, dependency chain and play values (ansible-core 2.16.20
   `lib/ansible/playbook/taggable.py:42`, `lib/ansible/playbook/block.py:310-361`).
2. **Include tags.** The `include_role` statement for keystone has tags `{keystone, haproxy, keepalived, loadbalancer}`.
3. **Dynamic include boundary.** `include_role` is *dynamic*. The included role's blocks get the `include_role` as
   parent (ansible-core 2.16.20 `lib/ansible/playbook/role_include.py:104,110-111`); an include is not statically
   loaded (`lib/ansible/playbook/task_include.py:50`), so `Block._get_parent_attribute` skips it and takes the
   grandparent's value (`lib/ansible/playbook/block.py:312-315`). So the tasks inside `keystone/tasks/loadbalancer.yml`
   would only carry the play tags, and would be filtered out under `-t keystone` (included blocks are filtered on
   tags, `lib/ansible/plugins/strategy/linear.py:272`).
4. **The `tags: always` workaround.** Kolla works around this with `tags: always` on the
   `import_role: loadbalancer-config` in every `loadbalancer.yml`, e.g.
   `ansible/roles/keystone/tasks/loadbalancer.yml:2-7`:
   ```yaml
   - name: "Configure loadbalancer for {{ project_name }}"
     import_role:
       name: loadbalancer-config
     vars:
       project_services: "{{ keystone_services }}"
     tags: always
   ```
   `loadbalancer-config` imports `haproxy-config` and, with ProxySQL, `proxysql-config`
   (`roles/loadbalancer-config/tasks/main.yml:2-8`). The same applies to `nova-cell`
   (`ansible/roles/nova-cell/tasks/loadbalancer.yml:56,93,130`, `proxy_loadbalancer.yml:19`,
   `cell_proxy_loadbalancer.yml:12`).
5. **Handlers ignore tags.** They run whenever they are notified (see common mechanics).

**`kolla-ansible -t keystone reconfigure`.** From the rules above and the tag test in ansible-core 2.16.20
`lib/ansible/playbook/taggable.py:69-79` (`always` always matches, 70-71):
- loadbalancer role tasks are **skipped**. They are tagged only with the play tags. That covers config-host,
  config.yml (haproxy.cfg, keepalived.conf, checks, pems, haproxy_run.sh, custom services.d, external-frontend.cfg,
  haproxy-ssh files) and check-containers.
- Exactly **one** `include_role` runs: keystone's (`site.yml:203-207`). It is skipped if `enable_keystone` is false.
  The other 38 `include_role` statements are skipped by tag.
- haproxy-config renders `/etc/kolla/haproxy/services.d/keystone.cfg` only (and, with the single external frontend,
  keystone's block of `external-frontend-map`), on every loadbalancer host. Only service keys that have a `haproxy:`
  dict and are enabled are rendered.
- If and only if one of those files changed, the `Restart haproxy container` handlers run at the end of the play:
  haproxy stops and starts on all backups at once, the play waits for their monitor port, then haproxy stops and
  starts on the VIP holder (1.5).
  - **keepalived is not restarted**, because nothing notifies its topic. Whether the VIP still moves because of (B) is
    NOT AVAILABLE.
- The restart re-reads **all** `services.d/*` files.
  - Any drift left in `/etc/kolla/haproxy/` by earlier runs (e.g. a previous `genconfig`, or stale files) goes live too.
  - Other services' `.cfg` files are **not re-rendered**. If another service's backend list changed (say, a new
    controller), it is not updated by `-t keystone`.
- Cert rotation for the VIP needs `-t haproxy` (or `-t loadbalancer`). The pem copy is a loadbalancer role task.
- `--skip-tags haproxy` skips the whole play, including all per-service includes: each one carries the inherited
  play tag, and a task with a skipped tag does not run (ansible-core 2.16.20 `lib/ansible/playbook/taggable.py:81-90`).
- Tag aliases:
  - `-t nova` hits both nova and nova-cell (252-265).
  - `-t memcache` (alias tag of the memcached play, `site.yml:413-414`) does **not** hit memcached's include, which is
    tagged only `memcached` (233-237).

**`kolla-ansible -t haproxy reconfigure`** (`-t keepalived` and `-t loadbalancer` select the same play and the same
tasks: they are all play tags, `site.yml:115-118`).
- **Still holds in 2024.1:** `common` does not run. The loadbalancer role runs `reconfigure.yml` → `deploy.yml`:
  config-host, config.yml (all files in 1.4), check-containers.
- **All 39** `include_role` statements match, through the inherited play tags. Every enabled service's
  `services.d/*.cfg` is re-rendered.
  - `placement`'s include has **no `when`** (`site.yml:248-251`). `placement-api.cfg` is always written, and is empty
    if `enable_placement` is false (`ansible/roles/placement/defaults/main.yml:7,13,20`).
- End-of-play handlers: the staged sequence of 1.5 for whichever topics were notified (haproxy, keepalived,
  proxysql), backups first, then the VIP holder, then the waits; then `Restart haproxy-ssh container` if notified.
- No service containers (keystone etc.) are touched.
- The `letsencrypt` play is not selected by these tags: it carries only the role tag `letsencrypt`
  (`site.yml:339-340`).

**`kolla-ansible reconfigure` (no tags).** Same as `-t haproxy`, plus all the other plays. It is still a single
staged haproxy restart per run, at the end of the loadbalancer play (the fix for LP#1864810/LP#1875228,
`releasenotes/notes/bug-1864810-5a5d0f91c0171b19.yaml`; role and `tasks:` share one flush, ansible-core 2.16.20
`lib/ansible/playbook/play.py:347-349`). The restart happens only if any rendered file changed or a container check
reported drift.

**`deploy-containers` and `-t <svc> deploy-containers`.** Only loadbalancer `check-containers.yml` runs, and only
under `-t haproxy`/`keepalived`/`loadbalancer` or no tags. The services.d includes do not run (`site.yml:326`).

---

## 2. `haproxy-config` role

### 2.1 How it is applied

- Only through `loadbalancer-config` (`roles/loadbalancer-config/tasks/main.yml:2-4`, when `haproxy_config_install`,
  true for every project except `mariadb` with ProxySQL, `roles/loadbalancer-config/defaults/main.yml:2`), which is
  imported (with `tags: always`) from the 39 `ansible/roles/*/tasks/loadbalancer.yml` files, which are
  `include_role`'d by the loadbalancer play (`site.yml:122-323`).
  - Every role that has a `loadbalancer.yml` is included; a diff of the two lists is empty.
  - `letsencrypt` has a `loadbalancer.yml` and an include, but its services define no `haproxy` entry
    (`roles/letsencrypt/defaults/main.yml:2-16`), so no frontend file is written for it (2.2).
  - `nova-cell` loops over cells (`ansible/roles/nova-cell/tasks/proxy_loadbalancer.yml:5-19` →
    `cell_proxy_loadbalancer.yml:3-12`, using `namespace_haproxy_for_cell`).
- No defaults-level `_services` dict of its own. It consumes `project_services`.

### 2.2 Task (`ansible/roles/haproxy-config/tasks/main.yml:2-21`), the only task

**Changed in 2024.1:** the role has three tasks. The template task is `roles/haproxy-config/tasks/main.yml:2-23`
(unchanged from 2023.1), then the new single-frontend map task (25-53), then the firewalld task (55-71).

```yaml
- name: "Copying over {{ project_name }} haproxy config"
  vars:
    service: "{{ item.value }}"
    haproxy_templates:
      - "{{ node_custom_config }}/haproxy-config/{{ inventory_hostname }}/{{ item.key }}.cfg"
      - "{{ node_custom_config }}/haproxy-config/{{ item.key }}.cfg"
      - "{{ node_custom_config }}/haproxy-config/{{ inventory_hostname }}/{{ haproxy_service_template }}"
      - "{{ node_custom_config }}/haproxy-config/{{ haproxy_service_template }}"
      - "templates/{{ haproxy_service_template }}"
    template_file: "{{ query('first_found', haproxy_templates) | first }}"
  template:
    src: "{{ template_file }}"
    dest: "{{ node_config_directory }}/haproxy/services.d/{{ item.key }}.cfg"
    mode: "0660"
  become: true
  when: [ service.enabled | bool, service.haproxy is defined, enable_haproxy | bool ]
  with_dict: "{{ project_services }}"
  notify: [ Restart haproxy container ]
```
- **Template choice.** `haproxy_service_template` defaults to `haproxy_single_service_split.cfg.j2` (frontend/backend
  split) (`roles/haproxy-config/defaults/main.yml:2`); it is the only template the role ships. Operators can override
  per service key (`<key>.cfg`), per host or globally under `/etc/kolla/config/haproxy-config/` (task lines 5-10).
- **New: single external frontend.** "Add configuration for {{ project_name }} when using single external frontend"
  (25-53) adds, with `blockinfile` and a `# BEGIN/END <service key>` marker, one line
  `<external_fqdn> <name>_back` per external, enabled HTTP entry that has a frontend, to
  `/etc/kolla/haproxy/external-frontend-map`, when `haproxy_single_external_frontend`; it notifies
  `Restart haproxy container`. The split template then skips the external HTTP frontends (148-152), and the
  loadbalancer role writes the shared `external_frontend` (1.4). Every `<svc>_public_port` then becomes
  `haproxy_single_external_frontend_public_port`, 443 with external TLS, else 80 (e.g. `group_vars/all.yml:335`,
  `:932`).
- **Firewalld.** "Configuring firewall for {{ project_name }}" opens each external service port in
  `external_api_firewalld_zone` when `enable_external_api_firewalld`, skipped for `kolla_action == "config"` (55-71).
- **Extras and health checks.**
  - Global extras: `haproxy_frontend_http_extra: [option httplog, option forwardfor]`,
    `haproxy_frontend_tcp_extra: [option tcplog]` and, new, `haproxy_frontend_redirect_extra: []`
    (`roles/haproxy-config/defaults/main.yml:5-12`).
  - Health check: `check inter 2000 rise 2 fall 5`, or with `check-ssl` (14-15).
- **Backend list.** From the split template:
  `{% for host in groups[host_group] %} … server {{ host_name }} {{ host_ip }}:{{ listen_port }} …`
  with `host_name = hostvars[host].ansible_facts.hostname` and `host_ip = 'api'|kolla_address(host)`
  (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:101-110`).
  - `host_group` defaults to `service.group` (134). `custom_member_list` overrides the list (85-88, 126).
    `active_passive` marks every server but the first as `backup` (109, 119), as in memcached.
  - Per-host weight: `haproxy_<service>_weight` in hostvars, 1-256 (104-108).
- **Binding and TLS.**
  - External entries bind `kolla_external_vip_address`; internal entries bind `kolla_internal_vip_address` (35-50).
  - External entries are dropped when `haproxy_enable_external_vip` is false (121).
  - **Changed in 2024.1:** TLS binds use `/etc/haproxy/certificates/haproxy.pem` and `…/haproxy-internal.pem` and add
    `alpn h2,http/1.1` when `haproxy_enable_http2` (default `yes`) (2-5; `group_vars/all.yml:920-921`). The redirect
    frontend now exempts `/.well-known/acme-challenge/` from the HTTPS redirect (53-56).
  - `tls_backend` adds `ssl verify required ca-file <haproxy_backend_cacert>` when `kolla_verify_tls_backend`, else
    `ssl verify none` (91-97).

### 2.3 Handler

It has none of its own. It notifies `Restart haproxy container`, a `listen` topic of the loadbalancer role's handlers
(`roles/loadbalancer/handlers/main.yml:18-21, :66-68, :109-111, :191-193, :243-245`). The topic is resolvable because
the loadbalancer role is in the same play.

`include_role` also *appends the included role's handlers* to the play (ansible-core 2.16.20
`lib/ansible/playbook/role_include.py:116-119`; `lib/ansible/plugins/strategy/linear.py:256`).
They are never notified here, so this is harmless.

### 2.4 Notable

- **Stale files are not removed** (see 1.8 D).
- If a service's `enabled` is false, the task is skipped and the file is left as it was. It is not emptied.
- **File name.** The file is named after the `<svc>_services` *key* (e.g. `keystone.cfg`, `placement-api.cfg`), not the
  project name. The map blocks use the same key as marker.
- **Facts are required.** It depends on facts for every backend host
  (`hostvars[host].ansible_facts.hostname`, split template line 102).
- **Precedence.** Variables come from the service role's defaults, evaluated on the loadbalancer host. Inventory or
  group_vars overrides of service variables therefore apply when set for the loadbalancer hosts or for `all`.
  - The backend weight is read from the backend host's own hostvars (`hostvars[host][service_weight]`, split template
    106-107).
  - NOT AVAILABLE: whether other per-host overrides set only on backend hosts are seen by haproxy-config, outside the
    places where the code explicitly uses `hostvars[…]` (nova-cell, the weight).

---

## 3. `memcached` role

### 3.1 Play

`site.yml:402-414`: hosts `memcached` ∩ `enable_memcached_True`, `serial: kolla_serial`, new `max_fail_percentage`
(408-411), role tags `[memcache, memcached]`. No meta dependency on `common` (no role has one in 2024.1). The default
inventory is `[memcached:children] control` (`inventory/multinode:116-117`).

### 3.2 `memcached_services` (`ansible/roles/memcached/defaults/main.yml:2-21`)

In 2024.1: `roles/memcached/defaults/main.yml:2-22`, unchanged from 2023.1.

| key | container | group | enabled | flags |
|---|---|---|---|---|
| memcached | `memcached` | memcached | `true` | not privileged; volumes are only config, localtime and timezone (45-48); a `healthcheck_listen` container healthcheck (32-43) |

- **Haproxy entry.** It has a haproxy sub-entry `memcached` (tcp, port `memcached_port` 11211, `group_vars/all.yml:493`)
  with `enabled: enable_memcached and enable_haproxy_memcached` (13).
  - `enable_haproxy_memcached: "no"` by default (`group_vars/all.yml:734-737`). The comment there: clients do
    client-side hashing.
  - Its backend list uses `active_passive: true` (22): the first host is active, the others are `backup`
    (section 2.2).
- **Tunables.** `memcached_connection_limit: "5000"` and `memcached_max_memory: "256"` (MB) (54, 57).
- **Container command:** `memcached -v -l <api_interface_address> -p 11211 -c 5000 -U 0 -m 256`
  (`templates/memcached.json.j2:2`), with `"config_files": []` (3).

### 3.3 Task flow

- `main.yml:2` is `include_tasks "{{ kolla_action }}.yml"` (no host guard).
- **deploy** = `config.yml` + `check-containers.yml` (`deploy.yml:2-4`). No flush; the handler runs at the end of the
  memcached play.
- **reconfigure** = deploy (`reconfigure.yml:2`).
- **upgrade** = config + check-containers (`upgrade.yml:2-4`).
- **deploy-containers** = check-containers.
- **pull** = service-images-pull.
- **stop** = service-stop.
- **precheck** = `service-precheck` + free port on `api_interface_address:11211` when the container is absent
  (`roles/memcached/tasks/precheck.yml:2-26`).
- **check** = empty.
- **config** = config.yml.
- Loadbalancer part: `roles/memcached/tasks/loadbalancer.yml:2-7`, through the loadbalancer play (`site.yml:233-237`,
  tag `memcached`).

### 3.4 Config files

- **Only `/etc/kolla/memcached/config.json`** (`roles/memcached/tasks/config.yml:13-26`), which notifies
  `Restart memcached container`.
- No custom-override path (there is no config file).
- The directory task has no group guard (`roles/memcached/tasks/config.yml:2-11`).

### 3.5 Handlers

- `Restart memcached container` (`roles/memcached/handlers/main.yml:2-15`): `recreate_or_restart_container`,
  `when: kolla_action != "config"`.
- It runs on all memcached hosts in parallel at the end of the play.

### 3.6 Bootstrap

None.

### 3.7 Dependencies (consumers of memcached)

- **Every service builds its memcache server list from `groups['memcached']`.**
  - 27 roles loop `for host in groups['memcached']` (grep over `ansible/roles`; 33 in 2023.1, which still had the
    removed services).
  - Keystone example: `backend = oslo_cache.memcache_pool` and
    `memcache_servers = {% for host in groups['memcached'] %}…`
    (`ansible/roles/keystone/templates/keystone.conf.j2:48-51`).
  - Horizon uses memcached as the **session store** when `horizon_backend_database` is false and the `memcached`
    group is not empty (`SESSION_ENGINE = 'django.contrib.sessions.backends.cache'`,
    `ansible/roles/horizon/templates/_9998-kolla-settings.py.j2:19-22`). **Changed in 2024.1:** that settings file
    replaces `local_settings.j2`, and `horizon_backend_database` now defaults to `false` (`group_vars/all.yml:1141`;
    2023.1 tied it to `enable_murano`).

### 3.8 Operationally notable

- **All memcached instances restart at once.** FACT: they restart simultaneously (serial 0); the container mounts no
  data volume (`roles/memcached/defaults/main.yml:45-48`) and its command has no persistence option
  (`templates/memcached.json.j2:2`).
  - NOT AVAILABLE: whether a restart therefore empties every cache at the same time, whether Horizon users are logged
    out (cache session backend), and whether the cold Keystone and keystonemiddleware token-validation caches give a
    load spike on Keystone and the DB.
  - Triggers are rare: a change of `api_interface_address`, port, memory or connection limit, or an image change on
    upgrade, plus, once, the unit-text drift after an upgrade from 2023.1 when no 2024.1 run has recreated or restarted
    the container
    ([F16](../findings.md#f16)). A change confined to `config.json` is only applied by a deploy/reconfigure that
    rewrites it; after a separate `genconfig`, `kolla_set_configs --check` sees no `config_files` to compare
    (kolla `docker/base/set_configs.py:556-559`; [F14](../findings.md#f14)).
- **Adding or removing a memcached host is expensive.** It changes the `memcache_servers` of almost every service
  config, which means a restart of most API containers on the next full reconfigure. That cost sits outside this role.
- **Tag aliases differ.** `-t memcache` reconfigures the container but not its haproxy file. Only `-t memcached` does
  both. With defaults the include renders no frontend (`enable_haproxy_memcached: "no"`), so the difference is not
  visible.
- **memcached has no `common` dependency.** Not specific to memcached: in 2024.1 no role has one.

---

## 4. `chrony` role

**Does not exist in 2024.1** (gone since 2023.1). `ansible/roles/` has no `chrony` directory, `site.yml` has no chrony
play (the first service play is "Apply role common", `site.yml:88-103`), the `group_by` list has no `enable_chrony`
entry (`site.yml:20-74`), `group_vars/all.yml` has no `enable_chrony` or `external_ntp_servers`, `inventory/multinode`
has no `chrony` or `chrony-server` group, and kolla 2024.1 has no `docker/chrony` image. Kolla-Ansible deploys no time
service; host time sync is only checked by `kolla-ansible prechecks` (`roles/prechecks/tasks/timesync_checks.yml:1-47`,
see [Chrony](../../components/chrony.md)). The subsections below keep their headings so that links still resolve.

### 4.1 Play

None in 2024.1 (see above). Ussuri ran a chrony play on every host, computes included, before haproxy.

### 4.2 `chrony_services` (Ussuri; removed)

Gone: there is no chrony role, so no `chrony` container, privileged or not, and no `chrony_bindaddress`.

### 4.3 Task flow

None in 2024.1. `-t chrony` selects only the `always`-tagged plays (fact gathering and host grouping).

### 4.4 Config files (`ansible/roles/chrony/tasks/config.yml`)

None: no `/etc/kolla/chrony/` files are written. No 2024.1 task stops, removes or checks a `chrony` container or its
configuration left on a host by an earlier release (the only `chrony` references under `ansible/` are in the precheck
of host services, `roles/prechecks/tasks/timesync_checks.yml:6-7,26`). What such a leftover container does is NOT
AVAILABLE.

### 4.5 Handlers

None.

### 4.6 Bootstrap

None.

### 4.7 Dependencies

- None of the Ussuri dependencies applies: the VIP is not a time source, `ip_nonlocal_bind` does not matter for
  chrony, and `external_ntp_servers` does not exist.
- The host NTP daemon is outside the Kolla-Ansible code. While `prechecks_enable_host_ntp_checks` is true (default,
  `roles/prechecks/defaults/main.yml:6`), the prechecks run `systemctl is-active` on `chrony`, `chronyd`, `ntp`, `ntpd`
  and `systemd-timesyncd` and fail on a non-zero return code, then fail unless `timedatectl status` prints
  `synchronized: yes` (`roles/prechecks/tasks/timesync_checks.yml:3-47`).
- ansible-collection-kolla (`bootstrap-servers`) neither installs nor configures an NTP daemon (no `chrony` in its
  `roles/`).

### 4.8 Operationally notable

- No chrony container restarts, steps the clock or runs on computes in 2024.1: the Ussuri items (low data-plane risk,
  cost per host, dependence on the haproxy group, the VIP as internal time source) do not apply.
- NOT AVAILABLE: which time source the hosts use. The precheck only proves that a listed daemon is active and that
  `timedatectl` reports a synchronised clock at precheck time; no deploy or reconfigure task checks it again.

---

## 5. `ovn` role

**Still holds in 2024.1:** the role is split into `ovn-controller` (container `ovn_controller`) and `ovn-db`
(containers `ovn_northd`, `ovn_nb_db`, `ovn_sb_db`), each with its own play. The anchors below keep the Ussuri `ovn`
names.

### 5.1 Play

Two plays:
- `site.yml:641-653`: hosts `ovn-controller` ∩ `enable_ovn_True`; `serial: kolla_serial`; new `max_fail_percentage`
  (647-650); role tags `[ovn, ovn-controller]`.
- `site.yml:655-669`: hosts `ovn-nb-db` ∪ `ovn-northd` ∪ `ovn-sb-db`, ∩ `enable_ovn_True`; `serial: kolla_serial`;
  new `max_fail_percentage` (663-666); role tags `[ovn, ovn-db]`.
- `enable_ovn: "{{ enable_neutron | bool and neutron_plugin_agent == 'ovn' }}"` (`group_vars/all.yml:834`).
- Default inventory (`inventory/multinode:593-613`):
  - `ovn-controller` = `ovn-controller-compute` (= compute) + `ovn-controller-network` (= network).
  - `ovn-database` = control.
  - `ovn-northd`, `ovn-nb-db` and `ovn-sb-db` are each `ovn-database`.
- So the `ovn-controller` play covers **all computes**. Both plays run after the openvswitch/ovs-dpdk plays and
  before neutron; `ovn-controller` runs before `ovn-db`.

### 5.2 `ovn_services` (Ussuri; now split)

In 2024.1: `ovn_controller_services` (`roles/ovn-controller/defaults/main.yml:2-9`) and `ovn_db_services`
(`roles/ovn-db/defaults/main.yml:2-23`).

| key | container | group | enabled | flags / volumes |
|---|---|---|---|---|
| ovn-controller | `ovn_controller` | ovn-controller | true | **`/run/openvswitch:/run/openvswitch:shared`**, kolla_logs (`ovn-controller/defaults/main.yml:22-26`); not privileged |
| ovn-northd | `ovn_northd` | ovn-northd | true | config, localtime, logs (`ovn-db/defaults/main.yml:47-50`) |
| ovn-nb-db | `ovn_nb_db` | ovn-nb-db | true | named volume **`ovn_nb_db:/var/lib/openvswitch/ovn-nb/`** (51-55) |
| ovn-sb-db | `ovn_sb_db` | ovn-sb-db | true | named volume **`ovn_sb_db:/var/lib/openvswitch/ovn-sb/`** (56-60) |

`ovn_remote_probe_interval: "60000"` (`ovn-controller/defaults/main.yml:36`), `ovn_openflow_probe_interval: "60"`
(38), `ovn_monitor_all: "false"` (40), `ovn_db_inactivity_probe: "60000"` (`ovn-db/defaults/main.yml:75`),
`ovn_leader_election_pause: 5` (98).

### 5.3 Task flow

- Both roles: `main.yml:2`: `include_tasks "{{ kolla_action }}.yml"`; `reconfigure.yml` and `upgrade.yml` import
  `deploy.yml`.
- **ovn-controller deploy** = `config.yml` → `check-containers.yml` → **`setup-ovs.yml`** → `meta: flush_handlers`
  (`roles/ovn-controller/tasks/deploy.yml:2-9`).
- **ovn-db deploy** = `lookup_cluster.yml` (on NB/SB hosts) → `bootstrap-initial.yml` (hosts without a DB volume) →
  `config.yml` → `check-containers.yml` → `meta: flush_handlers` → `bootstrap-db.yml` (hosts in both `ovn-nb-db` and
  `ovn-sb-db`) (`roles/ovn-db/tasks/deploy.yml:2-22`).
- **deploy-containers** = check-containers only (no setup-ovs, no cluster lookup or bootstrap, no explicit flush).
- **pull**/**stop** use the generic roles (`stop.yml` uses `ovn_controller_services` / `ovn_db_services`).
- **precheck**: ovn-db = free-port checks for 6641/6642 only (`roles/ovn-db/tasks/precheck.yml:2-32`);
  ovn-controller = empty. There is **no `service-precheck` group validation** in either role.
- **check** = none. **config** = config.yml.

**`setup-ovs.yml` runs on every deploy, reconfigure and upgrade of `ovn-controller`.** **Still holds in 2024.1:** each
task runs an Ansible module inside the `kolla_toolbox` container (`kolla_toolbox` with `module_name:
openvswitch_bridge` / `openvswitch_db`, with `container_engine`), whose result, `changed` included, is the inner
module's (`library/kolla_toolbox.py:113-131,145-197`). The second task runs only on `ovn-controller` hosts (40):

| task (lines) | hosts | effect |
|---|---|---|
| Create br-int bridge (2-11) | ovn-controller | `openvswitch_bridge` `br-int`, `fail_mode: secure` |
| Configure OVN in OVSDB (13-40), one loop item per key of `Open_vSwitch . external_ids` | ovn-controller | `ovn-encap-ip=<tunnel_interface_address>`, `ovn-encap-type=geneve`, `ovn-remote=<ovn_sb_connection>`, `ovn-remote-probe-interval`, `ovn-openflow-probe-interval`, `ovn-monitor-all` (31-36) |
| — `ovn-bridge-mappings` (37) | set on `ovn-controller-network`, or everywhere if `computes_need_external_bridge` (`group_vars/all.yml:1095`); **removed** elsewhere | `physnet1:<br>,…` from `neutron_bridge_name` (15) |
| — `ovn-chassis-mac-mappings` (38) | set on `ovn-controller-compute`, removed elsewhere | `physnetN:<random_mac seeded by host+bridge>` (16) |
| — `ovn-cms-options` (39) | set on `ovn-controller-network`, **removed** elsewhere | `enable-chassis-as-gw`, plus `,availability-zones=…` when `neutron_ovn_availability_zones` is set (17). This **overwrites** the whole value. |

### 5.4 Config files

Only `config.json` per service (`roles/ovn-controller/tasks/config.yml:15-26`, `roles/ovn-db/tasks/config.yml:15-26`),
which notifies `Restart <key> container`. There are no other files and no custom-override paths. The `config.json`
files have a `command` and a `permissions` entry for the log directory, but no `config_files`
(`roles/ovn-db/templates/ovn-nb-db.json.j2:1-10`, `roles/ovn-controller/templates/ovn-controller.json.j2:1-10`). The
entire configuration is on the command line:
- **ovn-nb-db and ovn-sb-db** (`roles/ovn-db/templates/ovn-nb-db.json.j2:2`, `ovn-sb-db.json.j2:2`), commands from
  `ovn_nb_command`/`ovn_sb_command` (`roles/ovn-db/defaults/main.yml:79-96`):
  - `/usr/share/ovn/scripts/ovn-ctl run_nb_ovsdb --db-nb-addr=<api ip> --db-nb-cluster-local-addr=<api ip> <bootstrap args> …`.
  - The bootstrap args are set only by `bootstrap-initial.yml` (section 5.6). For a new cluster, every host except
    `groups['ovn-nb-db'][0]` gets `--db-nb-cluster-remote-addr=<api ip of groups['ovn-nb-db'][0]>`
    (`bootstrap-initial.yml:5-13`); a member re-created on an existing cluster points at the current leader (59-67).
  - The client listener is set after the flush by `ovn-nbctl … set-connection ptcp:<6641>:0.0.0.0`
    (SB: `ovn-sbctl … ptcp:<6642>:0.0.0.0`) on the cluster leader (`roles/ovn-db/tasks/bootstrap-db.yml:21-33, :44-56`).
    Plaintext TCP, no SSL, on all IPv4 addresses. **Changed in 2024.1:** each `set-connection` is retried up to 3
    times, 5 s apart, until it returns 0 (30-32, 53-55), and the file's `docker exec` commands became
    `{{ kolla_container_engine }} exec` (e.g. 26).
- **ovn-northd** (`roles/ovn-db/templates/ovn-northd.json.j2:2`):
  `--ovnnb-db={{ ovn_nb_connection }} --ovnsb-db={{ ovn_sb_connection }}`.
  - Those are lists of all DB hosts (`group_vars/all.yml:548-549`).
- **ovn-controller** (`roles/ovn-controller/templates/ovn-controller.json.j2:2`):
  `ovn-controller … tcp:127.0.0.1:{{ ovsdb_port }}`, i.e. the local
  OVSDB on 6640 (`group_vars/all.yml:551`). The SB remote comes from `external_ids:ovn-remote` set by setup-ovs.

### 5.5 Handlers (`ansible/roles/ovn/handlers/main.yml`), in definition order

**Still holds in 2024.1:** `roles/ovn-db/handlers/main.yml` and `roles/ovn-controller/handlers/main.yml`, unchanged
apart from the module name.

1. `Restart ovn-nb-db container` (ovn-db 2-15): `recreate_or_restart_container`.
2. `Restart ovn-sb-db container` (ovn-db 17-30).
3. `Restart ovn-northd container` (ovn-db 32-45).
4. `Restart ovn-controller container` (ovn-controller 2-15), in its own play.

There are no `Wait for ovn-nb-db` / `Wait for ovn-sb-db` handlers. The `wait_for api_interface_address:6641/6642`
(timeout 60, `until success retries 10 delay 6`) runs as tasks at the end of `bootstrap-db.yml` (58-78), after the
flush, on hosts in both DB groups.

All handlers have `when: kolla_action != "config"`. There is no `run_once`, `serial` or rolling logic.
- **All NB members restart in the same step, then all SB members, then all northd.**
- The waits check only that the local TCP port is open. They do not check RAFT membership or leadership.

### 5.6 Bootstrap / registration

- No Keystone, MariaDB or RabbitMQ registration.
- **Cluster lookup** (`roles/ovn-db/tasks/lookup_cluster.yml`), on every deploy, reconfigure and upgrade: groups hosts
  by whether their `ovn_nb_db`/`ovn_sb_db` volume exists (2-19); on hosts
  that have it, fails the play (`any_errors_fatal`, 79, 132) when not every `ovn-nb-db`/`ovn-sb-db` host is in the
  current batch (32-42, 85-95), probes the port, asks each live member whether it is leader, and fails if the cluster
  exists with followers but no leader (44-77, 97-130).
- **Cluster creation and member bootstrap** (`roles/ovn-db/tasks/bootstrap-initial.yml`), only on hosts without a
  volume: on an existing cluster, an old member with the same IP is removed with `cluster/kick` on the leader
  (15-57); the bootstrap args are set (5-13, 59-67); config, check-containers and a flush start the containers
  (69-74); `bootstrap-db.yml` runs (76); the args are unset (78-81). The block is `any_errors_fatal` (83).
- **`bootstrap-db.yml`** (`deploy.yml:19-22`): when a cluster existed, a pause of `ovn_leader_election_pause` seconds
  (7-10); then `set-connection` on the NB and SB leaders (12-56), with no `changed_when`, so it reports *changed* on
  every run on the leader; then the port waits (58-78).
- **Chassis registration** (`setup-ovs.yml`) **re-runs on every deploy, reconfigure and upgrade** of `ovn-controller`.

### 5.7 Dependencies

- **openvswitch role.** setup-ovs does not exec into `openvswitch_vswitchd`; it needs the `kolla_toolbox` container
  (from the `common` play) and an OVSDB on the host's `/run/openvswitch`. **Changed in 2024.1:** `kolla_toolbox`
  mounts `/run/:/run/:shared` with Docker, and `/run/` without `:shared` plus the `run_default_volumes_podman`
  sub-mounts (`/run/openvswitch:/run/openvswitch:shared` among them) with Podman
  (`roles/common/defaults/main.yml:22,111`; `group_vars/all.yml:165-172`). `ovn_controller` itself connects to the
  local OVSDB on TCP 6640 (`ansible/roles/openvswitch/templates/start-ovsdb-server.j2:11`).
- **neutron.** `ml2_conf.ini.j2:39-40`, `ovn_agent.ini.j2:2-3` and `neutron_ovn_metadata_agent.ini.j2:17-18` use
  `ovn_nb_connection` and `ovn_sb_connection`.
  - Adding or removing a DB host therefore also needs a neutron reconfigure, and it changes the ovn-northd command
    line (restart on all northd hosts) and `ovn-remote` on every chassis.
- **Shared variables.** `neutron_bridge_name` (`group_vars/all.yml:1086`), `tunnel_interface_address` (316),
  `computes_need_external_bridge` (1095), `neutron_ovn_availability_zones` (1116).

### 5.8 Operationally notable

- **(A) The whole DB cluster restarts at once.** Any change to `ovn-nb-db`/`ovn-sb-db` restarts every member at once
  under serial 0 (`roles/ovn-db/handlers/main.yml:2-45`). That covers config.json, i.e. the IP or the bootstrap args,
  an image change on upgrade, and the unit-text drift after an upgrade from 2023.1 ([F16](../findings.md#f16)).
  - NOT AVAILABLE: whether RAFT loses quorum, how the neutron-server OVN driver and ovn-northd reconnect, and whether
    the data plane keeps its installed flows while the SB is unreachable.
  - **Still holds in 2024.1:** `ANSIBLE_SERIAL` (or a `--limit`) is not a mitigation on an existing cluster: when the
    batch holds a DB host that has its volume but not every `ovn-nb-db` (or `ovn-sb-db`) host, `lookup_cluster.yml`
    fails the play (`roles/ovn-db/tasks/lookup_cluster.yml:32-42, :85-95`).
- **(B) Whether the seed host is a single point of failure for re-deploys is NOT AVAILABLE.**
  - The first host is the seed only for a new cluster (no member has a volume and no leader is found,
    `bootstrap-initial.yml:5-13`). A member whose volume was lost is re-bootstrapped against the current leader, after
    its old entry is kicked (35-67). There is still no code for backups (grep: no `ovsdb-client backup` in
    `ansible/roles`).
  - NOT AVAILABLE: what happens when every volume is lost, or when no live member reports itself leader (the play
    then fails, `lookup_cluster.yml:73-77, :126-130`).
- **(C) ovn-controller restarts.** They happen on image or container-parameter change (upgrade, `deploy-containers`),
  on the one-time unit-text drift, or when a deploy/reconfigure rewrites its `config.json`, and hit **all computes and
  network nodes in parallel**. The OVN manifests have no `config_files` (`roles/ovn-db/templates/*.json.j2`,
  `roles/ovn-controller/templates/ovn-controller.json.j2`), so `kolla_set_configs --check` compares nothing and exits 0
  (kolla `docker/base/set_configs.py:556-559,562-582`): a command-line change written by `genconfig` is applied
  neither by `deploy-containers` nor by a later run, until the container restarts for another reason ([Kolla images
  §3](../../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
  - NOT AVAILABLE: whether this OVN release clears and re-installs OpenFlow flows on restart, and so whether there is
    a short data-plane interruption per chassis, plus north-south traffic loss when all gateway chassis (network nodes)
    restart together.
  - NOT AVAILABLE: whether there is also an SB DB reconnect storm whose size scales with the number of computes.
- **(D) Bootstrap cost scales with computes.** Each ovn-controller host runs 2 tasks, i.e. 10 `kolla_toolbox` module
  invocations (1 bridge + 9 `external_ids` keys, `setup-ovs.yml:2-40`), on every deploy, reconfigure and upgrade, each
  an `exec` of `ansible localhost -m <module>` in the `kolla_toolbox` container
  (`library/kolla_toolbox.py:113-131,163-165`).
  - NOT AVAILABLE: whether the `openvswitch_db`/`openvswitch_bridge` modules report changed on an unchanged host, and
    whether a changed `ovn_sb_connection` makes every chassis reconnect.
- **(E) Gateway options are clobbered.**
  - `ovn-cms-options` is *overwritten* on network nodes with `enable-chassis-as-gw` (plus `availability-zones=` from
    `neutron_ovn_availability_zones`) and *removed* on every other ovn-controller host, on every run
    (`roles/ovn-controller/tasks/setup-ovs.yml:17, :39`).
  - Any manual `ovn-cms-options` value, such as availability-zone hints, is overwritten or removed on every
    deploy/reconfigure (the code above); zones belong in `neutron_ovn_availability_zones`. The impact of losing a
    manual value is NOT AVAILABLE.
  - Bridge mappings are removed (`state: absent`) on hosts that are neither network nodes nor covered by
    `computes_need_external_bridge` (37).
- **(F) Security.** NB and SB clients connect over plain TCP (`ovn_nb_connection`/`ovn_sb_connection` use `tcp:`,
  `group_vars/all.yml:548-549`), and the DB listener is `ptcp:<port>:0.0.0.0` (`bootstrap-db.yml:28, :51`).
- **(G) OVN + DPDK cannot work in this release (inference from code):**
  - With `enable_ovs_dpdk` the openvswitch play is skipped (`site.yml:615,624`).
  - ovs-dpdk containers are only enabled when `neutron_plugin_agent in ['openvswitch']`
    (`ansible/roles/ovs-dpdk/defaults/main.yml:10,24`), and OVN requires `neutron_plugin_agent == 'ovn'`
    (`group_vars/all.yml:834`).
  - So with OVN and `enable_ovs_dpdk`, Kolla-Ansible deploys no Open vSwitch container at all, while setup-ovs and
    `ovn_controller` need an OVSDB (5.7). Whether OVN works with an OVSDB provided outside Kolla-Ansible is NOT
    AVAILABLE.
- **(H) Missing inventory groups are not caught.** There is no group validation precheck in either role. An old
  inventory without the `ovn-*` groups only surfaces as Jinja errors on `groups['ovn-…']`.

---

## 6. `ovs-dpdk` role

### 6.1 Play

`site.yml:626-639`: hosts `openvswitch` ∩ `enable_openvswitch_True_enable_ovs_dpdk_True`, `serial: kolla_serial`,
new `max_fail_percentage` (632-635), role tag `ovs-dpdk`.
- `enable_ovs_dpdk: "no"` (`group_vars/all.yml:835`).
- The openvswitch play is mutually exclusive with it (`site.yml:611-624`).
- Default `openvswitch` group = network, compute, manila-share (`inventory/multinode:105-108`).
- No `meta/` directory (no `common` dependency).

### 6.2 `ovsdpdk_services` (`ansible/roles/ovs-dpdk/defaults/main.yml:6-35`)

Unchanged from 2023.1 (the only difference in the file is a comment spelling).

| key | container | mapping | enabled | flags / volumes |
|---|---|---|---|---|
| ovsdpdk-db | `ovsdpdk_db` | `host_in_groups`: compute, manila-share (if enabled), neutron-dhcp-agent, -l3-agent, -metadata-agent (11-18) | `neutron_plugin_agent in ['openvswitch']` | `/run/openvswitch:shared`, named volume `ovsdpdk_db:/var/lib/openvswitch/` (71-77) |
| ovsdpdk-vswitchd | `ovsdpdk_vswitchd` | same expression (26-33) | same | **privileged: True**; **`/lib/modules:ro`, `/run/openvswitch:shared`, `/dev:/dev:shared`** (78-85) |

- Container commands: `start-ovsdb-server 127.0.0.1` and `ovs-vswitchd unix:/run/openvswitch/db.sock … --mlockall`
  (`roles/ovs-dpdk/templates/*.json.j2`).
- `neutron_bridge_name` is set in `group_vars/all.yml:1086`: `br_dpdk` when `enable_ovs_dpdk` (else `br-ex`, or
  `br-dvs` for vmware_dvs); the role has no default of its own.
- **Templating bug in `ovs_cidr_mappings`** (44), unchanged. For multiple bridges it emits the literal text
  `{neutron_bridge_name.split(',')[0]}` (single braces) instead of a Jinja expression.

### 6.3 Task flow

- **deploy** = `config.yml` → `check-containers.yml` → `meta: flush_handlers` (`roles/ovs-dpdk/tasks/deploy.yml:2-7`).
- **reconfigure** and **upgrade** = deploy.
- **deploy-containers** = check-containers.
- **precheck** = service-precheck (`roles/ovs-dpdk/tasks/precheck.yml:2-6`).
- **check** = empty.
- **config (genconfig)** = **config.yml**. This *includes host-mutating NIC binding* (see below).
- **pull.** Works: `roles/ovs-dpdk/vars/main.yml:4` sets `kolla_role_name: "ovsdpdk"`, and `service-images-pull`
  looks up `(kolla_role_name | default(project_name)) + '_services'`, i.e. `ovsdpdk_services`
  (`ansible/roles/service-images-pull/tasks/main.yml:2,14`).
- **stop** = service-stop with `ovsdpdk_services` (works).

`config.yml` key tasks (all of them run on deploy, reconfigure, upgrade **and genconfig**):
- **Config dirs and config.json** (2-26), gated by `enabled` and `host_in_groups`; the `config.json` copy has
  `become: true` (16).
- **"Copying ovs-dpdkctl tool"** (28-33). `copy src: ovs-dpdkctl.sh` (`roles/ovs-dpdk/files/ovs-dpdkctl.sh`), with
  `become` and **no `when`**.
- **"Install ovs-dpdkctl service and config"** (35-46). `command: ovs-dpdkctl.sh install`, which always reports
  changed and has no `when`. Inside `roles/ovs-dpdk/files/ovs-dpdkctl.sh` (`install`, 350-367):
  - `gen_config` runs **only if the conf file does not exist** (351-353). Later changes to bridge, port or cidr mappings
    in globals are **silently ignored**.
  - `modprobe` of the DPDK driver when it is not loaded, and persistence in `/etc/modules-load.d` or `/etc/modules`
    (`configure_kernel_modules`, 330-338).
  - Install and enable the `ovs-dpdkctl` systemd unit when its file is absent (355-357; `install_service`, 270-318),
    then `systemctl start ovs-dpdkctl` (362).
  - Rewrite the ifcfg or interfaces file for the bridge every run, and on RedHat start `ovs-dpdk-bridge`
    (`ovs-dpdkctl.sh:218-258, 363-366`).
- **"Binds the interface to the target driver specified in the config"** (48-59; the task name's spelling is fixed in
  2024.1). `ovs-dpdkctl.sh bind_nics` unbinds and rebinds the NICs listed in `port_mappings` when their current driver
  differs (`roles/ovs-dpdk/files/ovs-dpdkctl.sh:116-127`).
  - **This runs even under `kolla-ansible genconfig`.**
- **Changed in 2024.1, DPDK allow-list flag:** a generated configuration now lists the DPDK NICs with `-a <pci>`
  instead of `-w <pci>` (`ovs-dpdkctl.sh:45-56`); the value is stored in the conf file when it is generated (97) and
  read by `init` into `other_config:dpdk-extra` (171). Because the conf file is never regenerated, a host whose
  `ovs-dpdkctl.conf` was written by 2023.1 keeps `-w`. Whether the DPDK of the 2024.1 images accepts `-w` is NOT
  AVAILABLE.

### 6.4 Config files

- `/etc/kolla/ovsdpdk-{db,vswitchd}/config.json`, which notify their restart handlers.
- `/etc/kolla/ovsdpdk-db/ovs-dpdkctl.sh` and `/etc/kolla/ovsdpdk-db/ovs-dpdkctl.conf` (generated once).
- Systemd units `/etc/systemd/system/ovs-dpdkctl.service` and `ovs-dpdk-bridge.service`, plus the network ifcfg or
  interfaces file. These notify no handler.
- There are no custom-override paths.

### 6.5 Handlers (`ansible/roles/ovs-dpdk/handlers/main.yml`), in definition order

1. `Restart ovsdpdk-db container` (2-22). It **notifies 6 handlers** (16-22): wait db, bridges indexed, **Restart
   vswitchd**, bridges named, `Wait for dpdk tunnel ip`, `OVS-DPDK gather facts`.
   - **Changed in 2024.1: the 2023.1 "Likely BUG" is fixed.** The notify is now spelled `Wait for dpdk tunnel ip` (21),
     exactly the handler's name (88); 2023.1 notified `wait for dpdk tunnel ip`. ansible-core 2.16 matches the name
     exactly (ansible-core 2.16.20 `lib/ansible/plugins/strategy/__init__.py:546-553`), so the notify now reaches the
     handler, and no "handler not found" error is raised (`strategy/__init__.py:677-680`;
     `lib/ansible/config/base.yml:1293-1300`; kolla-ansible ships no `ansible.cfg`).
2. `Waiting the ovs db service to be ready` (24-34). `<engine> exec ovsdpdk_db ovs-vsctl --no-wait show`, retries 30
   delay 2.
3. `Ensuring ovsdpdk bridges are properly setup indexed` (36-52). `ovs-dpdkctl.sh init`, only if
   `ovs_physical_port_policy == 'indexed'`.
4. `Restart ovsdpdk-vswitchd container` (54-68).
5. `Ensuring ovsdpdk bridges are properly setup named` (70-86). `init`, when the policy is `named` (the default,
   `defaults/main.yml:54`).
6. **`Wait for dpdk tunnel ip`** (88-92). `wait_for: host: <dpdk_tunnel_interface_address> timeout: 300 sleep: 5`, with
   **no port and no path**, and no `when`.
   - `wait_for` then just does `time.sleep(timeout)` (ansible-core 2.16.20 `lib/ansible/modules/wait_for.py:541-542`).
   - So **every `ovsdpdk-db` restart now costs a fixed 300 s sleep**, on every DPDK host of the batch in parallel,
     before the play moves on. In 2023.1 the name mismatch kept this handler from running.
7. `OVS-DPDK gather facts` (94-102). `setup` re-gathers facts.

### 6.6 Bootstrap

OVS DB init (`ovs-dpdkctl.sh init`: `other_config:dpdk-*`, bridges, DPDK ports,
`roles/ovs-dpdk/files/ovs-dpdkctl.sh:164-216`) runs **only
from handlers**, i.e. when `ovsdpdk-db` restarts. It is not re-asserted on a plain reconfigure.

### 6.7 Dependencies

- neutron (openvswitch agent with `ovs_datapath: netdev`, `group_vars/all.yml:853`).
- Hugepages (`ovs_hugepage_mountpoint`, `defaults/main.yml:47`).
- `dpdk_tunnel_interface` (defaults to `neutron_external_interface`, `group_vars/all.yml:295`) and its address (318).
- `neutron_plugin_agent == 'openvswitch'`.

### 6.8 Operationally notable

- **Any `ovsdpdk-db` restart also restarts `ovs-vswitchd`.** That means an image change, config.json drift or the
  one-time unit-text drift after an upgrade from 2023.1 ([F16](../findings.md#f16)).
  - NOT AVAILABLE: whether this is a data-plane outage for all VMs on that host (vhost-user reconnect).
  - It happens **on all DPDK computes in parallel**, and is followed by the **300 s sleep** of 6.5 (changed in
    2024.1: the sleep now runs).
- **NIC rebinding and unit installation run on every deploy, reconfigure, upgrade and genconfig.** They are idempotent
  only as long as the driver already matches.
- **Sticky configuration.** `ovs-dpdkctl.conf` is never regenerated, so mapping changes, and the new `-a` flag, require
  deleting it manually.

---

## 7. `service-cert-copy` role

### 7.1 How it is applied

- `import_role: service-cert-copy` from `<role>/tasks/copy-certs.yml` in 38 roles (aodh … zun, plus `common` and
  `loadbalancer`; new: `letsencrypt`).
- Usually it is gated with `when: kolla_copy_ca_into_containers | bool or <svc>_enable_tls_backend | bool`, e.g.
  `ansible/roles/keystone/tasks/config.yml:41-43`.
- **loadbalancer gates only on `kolla_copy_ca_into_containers`** (`roles/loadbalancer/tasks/config.yml:249-251`).
- memcached, ovn-controller, ovn-db and ovs-dpdk do **not** use it.

### 7.2 Tasks (`ansible/roles/service-cert-copy/tasks/main.yml`)

Unchanged from 2023.1.

| task (lines) | dest | when | notifies |
|---|---|---|---|
| Copy extra CA certs (2-12) | `/etc/kolla/<item.key>/ca-certificates` from `{{kolla_certificates_dir}}/ca/` | `kolla_copy_ca_into_containers` | `Restart <item.key> container` |
| Backend TLS cert (14-34) | `/etc/kolla/<item.key>/<project_name>-cert.pem`. first_found: `certificates/<host>/<project>-cert.pem` → `certificates/<host>-cert.pem` → `certificates/<project>-cert.pem` → `kolla_tls_backend_cert` | the service has an enabled haproxy entry with `tls_backend` true, and not `kolla_externally_managed_cert` | `Restart <item.key> container` |
| Backend TLS key (36-56) | `…/<project_name>-key.pem` (mode 0600), with the same lookup order for `-key.pem` | same | same |

The loop is `with_dict: project_services | select_services_enabled_and_mapped_to_host`
(`kolla_ansible/filters.py:100-109`).

### 7.3 Notable

- **For the loadbalancer role, the loop includes `keepalived`** (and `proxysql`, and with Let's Encrypt
  `haproxy-ssh`, when enabled).
  - A CA bundle change (e.g. a root CA rotation with `kolla_copy_ca_into_containers: yes`) therefore notifies
    `Restart keepalived container` together with `Restart haproxy container`: the staged sequence of 1.5 with
    keepalived, i.e. backups first, then haproxy, proxysql and keepalived stopped on the VIP holder
    (`roles/loadbalancer/handlers/main.yml:36-49, :154-175, :210-222, :284-305`), and, with Let's Encrypt,
    `Restart haproxy-ssh container` on every host at once (`:331-345`).
  - Whether that moves or flaps the VIP is NOT AVAILABLE. `keepalived.json.j2` does not reference the CA files.
  - The kolla image does install them: keepalived starts through `kolla_start`, which runs `kolla_copy_cacerts` at every
    start. That script deletes the old `kolla-customca-*` entries and installs every file of
    `/var/lib/kolla/config_files/ca-certificates/` (kolla `docker/base/start.sh:16`, `docker/base/copy_cacerts.sh:6-27`;
    [Kolla images §2.4](../../concepts/kolla-images.md#24-kolla_copy_cacerts-and-kolla_httpd_setup)).
- **A CA or backend cert rotation restarts every container of every service using it** (whole fleet,
  per-play parallel).
- It is a pure file copy, with no expiry check.

---

## 8. `certificates.yml` playbook / `certificates` role

### 8.1 Play

`ansible/certificates.yml:1-11`:
- `import_playbook: gather-facts.yml` when `kolla_enable_tls_backend`, `rabbitmq_enable_tls` or
  `certificates_generate_libvirt` (2-6) (to obtain the API IPs of `tls-backend` hosts).
- Then `hosts: localhost`, `roles: [certificates]` (8-11).
- No serial, no tags, no `become`, no `max_fail_percentage`. It runs from `kolla-ansible certificates`
  (`tools/kolla-ansible:546-549`).
- The docs call it a "private test Certificate Authority" (`doc/source/admin/tls.rst:68-69`).

### 8.2 Flow (`ansible/roles/certificates/tasks/main.yml:2-6`)

In 2024.1 `roles/certificates/tasks/main.yml:2-8`: `generate-root.yml` → `generate.yml` → `generate-backend.yml`
(when `kolla_enable_tls_backend` or `rabbitmq_enable_tls`) → `generate-libvirt.yml` (when
`certificates_generate_libvirt`, default `libvirt_tls`, `roles/certificates/defaults/main.yml:9`).
- **Root CA** (`generate-root.yml`).
  - `root.key` RSA 4096 and `root.crt`, CN=KollaTestCA, **1024 days**, each guarded by `creates:` (14-33).
  - The CA is copied to `{{kolla_certificates_dir}}/ca/root.crt` (41-45). That is the source that
    `service-cert-copy` distributes.
- **External and internal certs** (`generate.yml`).
  - Key, CSR and cert with **365 days**, each `creates:`-guarded; the certs are signed with the `v3_req` extensions of
    the generated config.
  - They are assembled into `kolla_external_fqdn_cert` and `kolla_internal_fqdn_cert` (14-71, 86-144).
  - The internal cert is a copy of the external one when both TLS flags are on and the VIPs are the same (73-84).
  - **Changed in 2024.1:** all three blocks are skipped when `enable_letsencrypt` (70, 81, 142).
  - SAN: the VIP address as `IP.1`, plus the FQDN as `DNS.1` when it differs from the VIP
    (`templates/openssl-kolla.cnf.j2:15-19`, same in `openssl-kolla-internal.cnf.j2`).
- **Backend cert** (`generate-backend.yml`).
  - One shared cert (**500 days**) whose SANs are the API IPs of **all `tls-backend` hosts**
    (`templates/openssl-kolla-backend.cnf.j2:15-18`). **Changed in 2024.1:** the example inventory's `tls-backend`
    group is now `control` and `network` (`inventory/multinode:42-44`; 2023.1: `control` only).
  - Copied to `backend-cert.pem` and `backend-key.pem` (56-66), and, with `rabbitmq_enable_tls`, to
    `rabbitmq-cert.pem`/`rabbitmq-key.pem` (68-79).
- Global paths: `kolla_certificates_dir: "{{ node_config }}/certificates"` (`group_vars/all.yml:924`, normally
  `/etc/kolla/certificates`).

### 8.3 Notable

- **No rotation or renewal.** Every generating step is `creates:`-guarded, so re-running never renews expired
  certificates. External and internal certs expire after 365 days; the files must be deleted manually. (Let's Encrypt,
  new in 2024.1, is a separate role, not this playbook.)
- **Adding a `tls-backend` host does not update the backend SANs.** `backend.csr` and `backend.crt` exist
  (`generate-backend.yml:32,48`), so the cert is not re-issued. The same holds for a cloud whose `tls-backend` group
  grows because it adopts the new example inventory.
  - NOT AVAILABLE: whether haproxy then rejects the new backend with `kolla_verify_tls_backend: yes`
    (`group_vars/all.yml:944`).
- **Oddity in key generation.** The backend key task writes `private/backend/backend.key` but its `creates:` checks
  `kolla_tls_backend_key` (`generate-backend.yml:16-21`).
  - If an operator pre-supplies `backend-key.pem`, keygen is skipped but the CSR step still needs `backend.key`.
- **Distribution needs a separate run.** Certs only reach containers through `kolla-ansible -t haproxy reconfigure`
  (pem files) or a per-service reconfigure (backend and CA). Each of those means a container restart (sections 1.4 and
  7).

---

## 9. Cross-cutting summary: restart triggers and blast radius

| Component | Restarted when | Hosts at once (default) | Blast radius |
|---|---|---|---|
| haproxy | any `services.d`/haproxy.cfg/run.sh/pem/CA/config.json/external-frontend-map change, image change, any keepalived restart, unit-text drift ([F16](../findings.md#f16)) | all backups, then the VIP holder (all hosts at once if none holds the VIP) | all APIs plus MariaDB and other VIP traffic on the VIP holder while it restarts; VIP failover: NOT AVAILABLE |
| keepalived | keepalived.conf (inventory order!), config.json, checks, CA copy, image change | all backups, then the VIP holder (stopped last) | VIP move or outage: NOT AVAILABLE |
| haproxy_ssh (new) | its files, config.json, CA copy, image change (only with Let's Encrypt) | all loadbalancer hosts | certificate push by the lego container while it restarts: NOT AVAILABLE |
| memcached | config.json (IP, port, memory, limit), image | all memcached hosts | whether all caches are emptied and Horizon users logged out: NOT AVAILABLE |
| chrony | no chrony role in 2024.1 | n/a | n/a |
| ovn-nb/sb-db | config.json (IPs, bootstrap args), image | all DB hosts | NB/SB API down; quorum re-election: NOT AVAILABLE |
| ovn-northd | NB/SB host list, image | all northd hosts | logical-flow processing pause: NOT AVAILABLE |
| ovn-controller | image, drift | **all computes and network nodes** | data-plane blip per chassis: NOT AVAILABLE |
| ovsdpdk-db → vswitchd | image, drift (db restart always notifies the vswitchd restart) | **all DPDK hosts** | VM data-plane outage: NOT AVAILABLE; **new in 2024.1:** followed by a fixed 300 s sleep (6.5) |

Things that run on **every** reconfigure, regardless of changes:
- loadbalancer config-host (sysctl role/modprobe) and the template set, plus 39 service includes (`-t haproxy` or no
  tags).
- OVN setup-ovs (10 `kolla_toolbox` module calls per chassis), the OVN DB cluster lookup and the leader
  `set-connection`.
- ovs-dpdk `install` + `bind_nics` (per DPDK host, **also on genconfig**).
- `compare_container` with an `<engine> exec kolla_set_configs --check` for every container on every host.

Things whose cost scales with the number of computes: ovn-controller config + setup-ovs, ovs-dpdk. The load
balancer, memcached, the OVN DB and certificates scale only with control or loadbalancer hosts. Chrony does not run on
computes.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
