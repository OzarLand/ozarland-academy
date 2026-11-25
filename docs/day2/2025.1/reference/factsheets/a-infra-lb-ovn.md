---
title: Fact sheet A
description: "Fact sheet for the loadbalancer, haproxy-config, memcached, OVN, ovs-dpdk and service-cert-copy roles and the certificates playbook, 2025.1."
tags: [haproxy, keepalived, memcached, chrony, ovn, handlers, tags, serial]
---

# Fact sheet A

Scope: roles `haproxy` (in 2025.1, as since 2023.1, the `loadbalancer` role: haproxy, keepalived, proxysql, `haproxy_ssh`, and the per-service `loadbalancer.yml` fan-out), `haproxy-config`, `memcached`, `chrony` (gone since
2023.1), `ovn` (the `ovn-controller` and `ovn-db` roles), `ovs-dpdk`, `service-cert-copy`, and the `certificates.yml`
playbook/role.

Sources: kolla-ansible tag `2025.1-eom` (commit `7222f0f`), kolla `2025.1-eom` (commit `c4b53a2`). Paths that start
with `ansible/`, `tools/`, `kolla_ansible/`, `releasenotes/` or `doc/` are relative to the kolla-ansible repository
root; other kolla-ansible paths are relative to `ansible/`. Supported Ansible: ansible-core 2.17 to 2.18 (`requirements.txt:14`); this sheet cites ansible-core 2.18.20, the only version read (2.17 is NOT AVAILABLE).

How the evidence was gathered:
- **Code reading.** Every claim cites `path:line` in the 2025.1 trees.
- **Ansible semantics.** Tag inheritance, handler order and serial batches cite the ansible-core 2.18.20 source as
  ansible-core 2.18.20 `lib/ansible/<path>:N`. Ansible's own parse of `site.yml` is in
  [list-tags-site.txt](../listings/list-tags-site.txt).
- **Labels.** A claim with a `path:line` citation is a FACT read from the sources. `NOT AVAILABLE` marks what the
  sources do not establish, for example timings, runtime outcomes and anything about Podman on a real host.

> [!NOTE]
> **Key answers**
>
> - **Changed in 2025.1, who restarts:** no config task of these roles notifies a handler any more; each role's
>   `check-containers.yml` imports `service-check-containers`, which notifies `Restart <name> container` only for the
>   containers `compare_container` reports changed (`roles/service-check-containers/tasks/main.yml:4-41`). For the load
>   balancer that compare also runs once more at the end of the play, from an include that carries only the play
>   tags (`site.yml:319-324`), so **`-t <service>` rewrites the service's HAProxy file but no longer restarts HAProxy**
>   ([1.9](#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy), [F18](../findings.md#f18)).
> - **Changed in 2025.1, load balancer:** ProxySQL on by default, TLS 1.3 only by default, `haproxy_run.sh` `exec`s
>   HAProxy, the keepalived ProxySQL check logs in with the admin password, the PEM copies moved to `copy-certs.yml`,
>   and a backup that does not come back now stops the play on every host (`group_vars/all.yml:441, :958`;
>   `roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38`;
>   `roles/loadbalancer/handlers/main.yml:119, :154`) ([1.2](#12-haproxy_services-ussuri-now-loadbalancer_services),
>   [1.5](#15-handlers-ansibleroleshaproxyhandlersmainyml-definition-order--run-order-see-common-mechanics)).
> - **New in 2025.1, OVN Southbound relays:** on by default, one relay per 50 `ovn-controller` hosts; the chassis and
>   the OVN agents connect to a relay, northd and neutron-server to the cluster (`group_vars/all.yml:640-648, :953`).
>   The `ovn-controller` play runs first and points the chassis at relays that the `ovn-db` play creates afterwards
>   ([5.8](#58-operationally-notable), item I; NOT AVAILABLE what that does, to be confirmed by the community).
> - **Still holds:** a haproxy-relevant change is a staged stop/start of haproxy (backups first, then the VIP holder),
>   never a reload by Kolla-Ansible; stale `services.d` files are never removed; the OVN DB cluster and every
>   `ovn_controller` restart together under the default serial, which `reconfigure` and `upgrade` can no longer change
>   ([F19](../findings.md#f19)); `ovs-dpdkctl.sh install`/`bind_nics` run on every deploy, reconfigure, upgrade and
>   genconfig, and every `ovsdpdk-db` restart sleeps 300 s; certificates are never renewed
>   ([9](#9-cross-cutting-summary-restart-triggers-and-blast-radius)).

Common mechanics that apply to every role below (all verified in code):
- **All containers use host networking.** The container module is `kolla_container`; its Docker worker always
  sets `'network_mode': 'host'` (`module_utils/kolla_docker_worker.py:285-287`), and the Podman worker does too
  (`module_utils/kolla_podman_worker.py:77`). "net=host" is therefore never a role flag. `kolla_container_engine`
  defaults to `docker` (`ansible/group_vars/all.yml:100`); this sheet follows the Docker path, and how Podman behaves
  on a host is NOT AVAILABLE.
- **A config-only change means a full stop+start.** `config_strategy: "COPY_ALWAYS"` (`ansible/group_vars/all.yml:49`)
  is passed as `KOLLA_CONFIG_STRATEGY` in `docker_common_options` (`ansible/group_vars/all.yml:151-162`). With
  COPY_ALWAYS and no parameter drift, `recreate_or_restart_container` calls `restart_container`
  (`module_utils/kolla_docker_worker.py:352-374`). **Still holds in 2025.1:** for a container with a systemd unit
  (every container except one-shot ones) that is a systemd `RestartUnit` of `kolla-<name>-container.service`, after the
  unit file is rewritten when it differs (`module_utils/kolla_docker_worker.py:450-470`,
  `module_utils/kolla_systemd_worker.py:72,107-114,173-186`). The unit's `ExecStop` is now
  `/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:33`), and
  `graceful_timeout` keeps the `common_options` value, `docker_graceful_timeout: 60` (`library/kolla_container.py:311`, `:357-389`; `ansible/group_vars/all.yml:148,160`) ([R24](../../risk/risk-register.md#r24)).
- **Changed in 2025.1, unit text:** the unit template changed again (`PartOf=kolla.target`), and `compare_container` compares the whole unit text
  (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_systemd_worker.py:155-168`). The first 2025.1 check of a container whose unit 2024.1 wrote reports drift, and the restart handler runs ([F16](../findings.md#f16)). This applies to every container of this sheet that no 2025.1 run has recreated or restarted yet.
- **There is no "reload" path in the roles in scope.** The haproxy image still ships a reload helper,
  `kolla_ensure_haproxy_latest_config` (kolla `docker/haproxy/haproxy/Dockerfile.j2:17,21`,
  `docker/haproxy/haproxy/ensure_latest_config.sh:5-14`), but kolla-ansible 2025.1 never calls it (grep finds no caller). The helper would not reload haproxy here anyway: it signals `haproxy-systemd-wrapper` (`:11`), which `haproxy_run.sh` does not start: it `exec`s `/usr/sbin/haproxy` itself (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38`). **Since 2024.1:**
  with `enable_letsencrypt`, a renewed certificate is loaded into the running haproxy through its admin socket
  (`set ssl cert`, `commit ssl cert`) by the `haproxy_ssh` image's `update-loadbalancer-cert` (renamed from `update-haproxy-cert` in 2025.1), called over SSH by the lego container (kolla `docker/haproxy/haproxy-ssh/update-loadbalancer-cert.sh:23,50,123-125`,
  `docker/letsencrypt/letsencrypt-lego/sync-and-update-certificate.sh:83-89`). That path is outside the
  Kolla-Ansible handlers.
- **`kolla_serial` is forced for two actions.** The CLI sets it only for `reconfigure` and `upgrade` (`kolla_ansible/cli/commands.py:136, :278`), to the constant `ANSIBLE_SERIAL = 0` = all hosts at once (`kolla_ansible/cli/commands.py:22`); these extra vars come after the user's `-e`, so neither action can be batched ([F19](../findings.md#f19)). The other actions leave it unset, and every play falls back to `0`; `deploy -e kolla_serial=N` batches.
- **Since 2024.1, `max_fail_percentage` on every play.** Each play in scope sets
  `max_fail_percentage: {{ <play>_max_fail_percentage | default(kolla_max_fail_percentage) | default(100) }}`
  (e.g. `ansible/site.yml:111-114`). It counts the failures of the current batch only: `PlaybookExecutor` runs
  `TaskQueueManager.run()` once per batch (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:182-188`)
  and `run()` clears `_failed_hosts` (`lib/ansible/executor/task_queue_manager.py:326-334`); with 100 it never stops a
  play early.
- **Handlers fire in definition order across all hosts of the batch in lockstep** (linear strategy).
  - With the default serial 0, a handler restarts that container on **every host of the play at the same time**
    (unless the handler itself selects hosts, as the loadbalancer handlers do, section 1.5).
  - In ansible-core 2.18 a notification is first saved per host by name (ansible-core 2.18.20
    `lib/ansible/plugins/strategy/__init__.py:653-674`, `lib/ansible/executor/play_iterator.py:648-652`) and
    resolved to handlers at the flush (`lib/ansible/plugins/strategy/__init__.py:951-961`). A name reaches the handler of that exact name
    and every handler that `listen`s to it (`lib/ansible/plugins/strategy/__init__.py:510-559`). At a flush, every host walks the play's
    handler list in definition order and runs the handlers it was notified for (`lib/ansible/executor/play_iterator.py:198,424-443`); the
    linear strategy keeps the hosts on the same handler (`lib/ansible/plugins/strategy/linear.py:47-90`). A notify sent
    by a handler while handlers run is applied at once (`lib/ansible/plugins/strategy/__init__.py:656-661`), so a handler defined later
    and notified that way runs in the same flush.
- **Handlers are not tag-filtered in ansible-core 2.18.**
  - Tags filter only the play's compiled task blocks and the blocks of non-handler includes (ansible-core 2.18.20
    `lib/ansible/executor/play_iterator.py:187-191`, `lib/ansible/plugins/strategy/linear.py:260-275`). The handler
    list is copied unfiltered (`lib/ansible/executor/play_iterator.py:198`) and handler selection has no tag check
    (`lib/ansible/executor/play_iterator.py:424-443`). So under `-t <service>` the handlers listening to `Restart haproxy container` still
    run, although they only carry the inherited play tags `haproxy`, `keepalived`, `loadbalancer`.

---

## 0. Plays in `ansible/site.yml` (summary table)

| Role | Play (lines) | Host pattern | Tags | serial |
|---|---|---|---|---|
| chrony | **none since 2023.1**: no chrony play, role, group or image ([Chrony](../../components/chrony.md)) | n/a | n/a | n/a |
| haproxy (+keepalived) | role `loadbalancer`, `site.yml:105-327` | `loadbalancer`, `&enable_loadbalancer_True` (107-109) | **play-level** `haproxy`, `keepalived`, `loadbalancer` (115-118) | `kolla_serial` (110) |
| haproxy-config | no play of its own. 38× `include_role <svc> tasks_from: loadbalancer` in a `block`, inside the loadbalancer play (`site.yml:121-318`), then one final `include_role loadbalancer tasks_from: check-containers` (`site.yml:319-324`, new in 2025.1) | loadbalancer hosts | per include: `<svc>`; nova/nova-cell: `[nova, nova-api]` / `[nova, nova-cell]` (`site.yml:252-265`). Plus the inherited play tags | inherited |
| memcached | `site.yml:417-429` | `memcached`, `&enable_memcached_True` (419-421) | role-level `[memcache, memcached]` (428-429) | `kolla_serial` (422) |
| ovs-dpdk | `site.yml:620-633` | `openvswitch`, `&enable_openvswitch_True_enable_ovs_dpdk_True` (622-624) | role-level `ovs-dpdk` (631-633) | `kolla_serial` (625) |
| ovn | two plays: `ovn-controller` `site.yml:635-647`, `ovn-db` `site.yml:649-663` | `ovn-controller` / `ovn-nb-db`, `ovn-northd`, `ovn-sb-db`; each `&enable_ovn_True` | role-level `[ovn, ovn-controller]` (646-647) / `[ovn, ovn-db]` (662-663) | `kolla_serial` (640, 656) |
| service-cert-copy | no play. Imported from `<role>/tasks/copy-certs.yml` (40 roles, including `loadbalancer`) | caller's | caller's | caller's |
| certificates | separate playbook `ansible/certificates.yml:1-10` (`kolla-ansible certificates`, `kolla_ansible/cli/commands.py:187-195`) | `localhost` | none | none |

- **Every play in scope also sets `max_fail_percentage`** (default 100), e.g. `site.yml:111-114`, `:423-426`,
  `:626-629`, `:641-644`, `:657-660` (see common mechanics). The certificates play does not
  (`ansible/certificates.yml:7-10`).
- **Pattern groups.** The `enable_*` pattern groups are created by `group_by` in `site.yml:20-75`:
  - loadbalancer line 48 (`enable_loadbalancer` = haproxy or keepalived or proxysql enabled, `group_vars/all.yml:838`),
    memcached 53, openvswitch/ovs_dpdk 61, ovn 62, letsencrypt 47. There is no chrony entry. New in 2025.1: valkey 71;
    swift is gone.
- **Play order matters.** It runs common (88) → loadbalancer (105) → letsencrypt (329) → … valkey (399, new) →
  `mariadb.yml` (415) → memcached (417) → … placement (591) → openvswitch (605) → ovs-dpdk (620) → ovn-controller (635)
  → ovn-db (649) → **`nova.yml` (667)** → neutron (669). **Changed in 2025.1:** `nova.yml` now runs after the OVS and
  OVN plays (2024.1 imported it just before the openvswitch play).

## 1. `haproxy` role (haproxy + keepalived)

**Still holds in 2025.1:** this role is `loadbalancer` (`ansible/roles/loadbalancer/`). It runs `haproxy`, `keepalived`
and, with `enable_proxysql`, `proxysql`; **changed in 2025.1:** `enable_proxysql` defaults to `yes`
(`group_vars/all.yml:958`). With `enable_letsencrypt` (default `no`, `group_vars/all.yml:913`) it also runs
`haproxy_ssh`. ProxySQL and `haproxy_ssh` are described here only where they change the haproxy/keepalived behaviour;
the database side of ProxySQL is on [MariaDB/Galera](../../components/mariadb.md).

### 1.1 Play

- **Play:** `site.yml:105-327`. Hosts `loadbalancer` ∩ `enable_loadbalancer_True`, `serial: kolla_serial`,
  `max_fail_percentage` (111-114), play-level `tags: [haproxy, keepalived, loadbalancer]` (115-118).
- **Role entry:** `- { role: loadbalancer }` (120), with no `when`.
- **The loadbalancer block.** The play then has a `tasks:` block (121-327) of 38 per-service `include_role` statements
  (39 in 2024.1: the swift include is gone) and, **new in 2025.1**, a last
  `include_role: name: loadbalancer, tasks_from: check-containers` with `when: kolla_action != 'config'`
  (`site.yml:319-324`). The block is guarded by (325-327):
  ```yaml
  when:
    - enable_haproxy | bool
    - kolla_action in ['deploy', 'reconfigure', 'upgrade', 'config']
  ```
  The final include carries only the inherited play tags; section 1.9 shows what that changes for `-t <service>`.
- **Role entry point.** `roles/loadbalancer/tasks/main.yml:2-3` is
  `include_tasks: "{{ kolla_action }}.yml"` with `when: inventory_hostname in groups['loadbalancer']`.
- **Default inventory.** `[loadbalancer:children] network` (`ansible/inventory/multinode:84-85`). There is no
  `haproxy` group. `[letsencrypt:children] loadbalancer` (`ansible/inventory/multinode:188-189`).

### 1.2 `haproxy_services` (Ussuri; now `loadbalancer_services`)

Since 2023.1 the dict is `loadbalancer_services` (`roles/loadbalancer/defaults/main.yml:2-36`); in 2025.1 only the
image names changed (they gain `docker_image_name_prefix`, and the ProxySQL image a `-3` suffix when
`proxysql_version` is 3, `roles/loadbalancer/defaults/main.yml:42-56, :238`).

| key | container | group | enabled | privileged | notable volumes |
|---|---|---|---|---|---|
| haproxy | `haproxy` | loadbalancer | `true` | **True** | `/etc/kolla/haproxy/:/var/lib/kolla/config_files/:ro`, named volume `haproxy_socket:/var/lib/kolla/haproxy/`, named volume `letsencrypt_certificates:/etc/haproxy/certificates` (116-121) |
| proxysql | `proxysql` | loadbalancer | `enable_proxysql` (**default `yes`**) | False | `kolla_logs`, `proxysql:/var/lib/proxysql/`, `proxysql_socket:/var/lib/kolla/proxysql/` (123-129) |
| keepalived | `keepalived` | loadbalancer | `enable_keepalived` | **True** | `/lib/modules:/lib/modules:ro`, `haproxy_socket` when `enable_haproxy`, `proxysql_socket` when `enable_proxysql` (130-136) |
| haproxy-ssh | `haproxy_ssh` | loadbalancer | `enable_letsencrypt` | not set (False) | `haproxy_socket`, and with letsencrypt `letsencrypt:/etc/letsencrypt` and `letsencrypt_certificates:/etc/haproxy/certificates` (137-143); no `_extra_volumes` |

- **Keepalived default.** `enable_keepalived: "{{ enable_haproxy | bool }}"` (`ansible/group_vars/all.yml:837`) and
  `enable_haproxy: "yes"` (836).
- **Since 2024.1, haproxy volumes.** The `letsencrypt_certificates` volume is always mounted, with or without
  Let's Encrypt (`roles/loadbalancer/defaults/main.yml:121`).
- **Shared socket volume.** The `haproxy_socket` volume is shared between haproxy, keepalived and `haproxy_ssh`.
  The haproxy stats socket is `stats socket /var/lib/kolla/haproxy/haproxy.sock`, with `level admin` when
  `haproxy_socket_level_admin` (`roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:13`), which follows
  `enable_letsencrypt` (`roles/loadbalancer/defaults/main.yml:185`).
  - **Still holds in 2025.1:** the keepalived health check is rendered by kolla-ansible. `config.yml` writes one
    `check_alive_<service>.sh` per enabled haproxy/proxysql service into `/etc/kolla/keepalived/checks/`
    (`roles/loadbalancer/tasks/config.yml:90-105`) and removes those of disabled services (74-88); both tasks skip
    `haproxy-ssh` (85, 103) and run only with `keepalived_track_script_enabled` (83, 100). **Changed in 2025.1:**
    neither task notifies a handler any more. keepalived's `config.json` copies that directory to `/checks`
    (`templates/keepalived/keepalived.json.j2:10-15`). The haproxy check runs
    `echo "show info" | socat unix-connect:/var/lib/kolla/haproxy/haproxy.sock stdio`
    (`templates/keepalived/check_alive_haproxy.sh.j2:6`). **Changed in 2025.1:** the proxysql check runs
    `mariadb … --user=<proxysql_admin_user> --password=<proxysql_admin_password> -e "SELECT 1"` on the ProxySQL admin
    socket (`roles/loadbalancer/templates/keepalived/check_alive_proxysql.sh.j2:6-12`), instead of a `socat`
    `show info`, so the rendered check now holds the ProxySQL admin password. The image's `/check_alive.sh` runs every
    file under `/checks` and fails if one fails (kolla `docker/keepalived/check_alive.sh:9-32`, baked in by kolla
    `docker/keepalived/Dockerfile.j2:25,29`).
- Haproxy, proxysql and `haproxy_ssh` have a container healthcheck (`roles/loadbalancer/defaults/main.yml:76-113`;
  haproxy: a `healthcheck_curl` of the monitor port on `api_interface_address`, 80; `haproxy_ssh`:
  `healthcheck_listen sshd`, 106). keepalived has none (21-28).
- No pid_mode or ipc_mode is set.

### 1.3 Task flow per `kolla_action`

| action | task files (in order) | notes |
|---|---|---|
| deploy | `config-host.yml` → `config.yml` → `check-containers.yml` (`roles/loadbalancer/tasks/deploy.yml:2-6`) | **No `flush_handlers`.** Comment `roles/loadbalancer/tasks/deploy.yml:8-11`: "haproxy role handlers should not be flushed early. site.yml handles all haproxy things in a dedicated play… See bug 1875228". The per-service loadbalancer includes then run (site.yml block), **then the final `check-containers` include runs a second compare (new in 2025.1, `site.yml:319-324`)**, and the handlers flush once at the end of the play. |
| reconfigure | `roles/loadbalancer/tasks/reconfigure.yml:2` → `import_tasks: deploy.yml` | identical to deploy |
| upgrade | first `stop_and_remove_container` of `prometheus_haproxy_exporter` and removal of `/etc/kolla/prometheus-haproxy-exporter` on loadbalancer hosts (`roles/loadbalancer/tasks/upgrade.yml:4-19`, unchanged since 2024.1), then `import_tasks: deploy.yml` (21) | otherwise identical to deploy; the staged handlers (1.5) apply image changes. See 1.8 (F). |
| deploy-containers | `check-containers.yml` (`roles/loadbalancer/tasks/deploy-containers.yml:2`) | the loadbalancer block is **not** run (`site.yml:327`) |
| pull | `service-images-pull` (`roles/loadbalancer/tasks/pull.yml:2-3`): pulls the images of `loadbalancer_services` (`project_name: "loadbalancer"`, `roles/loadbalancer/vars/main.yml:2`) | `haproxy_ssh` only where enabled |
| stop | `service-stop` with `loadbalancer_services` (`roles/loadbalancer/tasks/stop.yml:2-6`) | stops **haproxy, keepalived (and proxysql, haproxy_ssh) on all loadbalancer hosts**, so no API frontend runs; whether the VIP is then released is NOT AVAILABLE. `skip_stop_containers` can exclude them (`ansible/roles/service-stop/tasks/main.yml:11-12`). |
| precheck | `precheck.yml` (760 lines, 57 named top-level tasks) | `service-precheck` group validation (2-6). Container facts (8-18) and grouping by running container (20-45). Whole-batch detection for the VIP checks (47-56, which skip when `--limit`/serial does not cover all loadbalancer hosts). Cert existence on localhost (57-95), skipped for the certificates that Let's Encrypt manages (`letsencrypt_managed_certs`, 74, 93). External VIP iface present/active (96-109). VIPs not pingable (111-123, only when keepalived runs nowhere). Free ports for stats, monitor, ProxySQL admin and, **new**, the ProxySQL Prometheus exporter (125-213). VIP in the same subnet as `api_interface` (215-228). `show stat` through the socket (230-241). Then one "free port" check per service on the VIP (from 242), skipped when that frontend already exists in `haproxy_stat`, and firewalld checks at the end when `enable_external_api_firewalld` (741-760). |
| check | **new in 2025.1:** `check.yml` imports `service-check` (`roles/loadbalancer/tasks/check.yml:2-4`) | see [`kolla-ansible check`](../../operations/command-quick-lookup.md) |
| config (genconfig) | `config.yml` only (no `config-host.yml`). The loadbalancer block **does** run (`'config'` is in the list, `site.yml:327`), but its final `check-containers` include does not (`site.yml:324`). | No config task notifies, and the loadbalancer handlers keep `when: kolla_action != "config"` (`roles/loadbalancer/handlers/main.yml:16-17`, …, `:346-347`), so nothing restarts. The next run of the play with a compare detects the drift through `kolla_set_configs --check` and restarts ([F14](../findings.md#f14)). |

**Key tasks:**
- **`roles/loadbalancer/tasks/config-host.yml:3-25`.** These run on deploy, reconfigure and upgrade:
  - The sysctl writes go through the `sysctl` role (`include_role`, 8-18), only when `set_sysctl` (default `yes`,
    `group_vars/all.yml:816`): `net.ipv6.ip_nonlocal_bind=1`, `net.ipv4.ip_nonlocal_bind=1`,
    `net.ipv4.tcp_retries2=<haproxy_host_ipv4_tcp_retries2>`, `net.unix.max_dgram_qlen=128` (12-16), written to
    `kolla_sysctl_conf_path` (`/etc/sysctl.conf`, `group_vars/all.yml:819`) by `roles/sysctl/tasks/main.yml:7-20`.
  - `KOLLA_UNSET` (the default, `roles/loadbalancer/defaults/main.yml:182`) means `state: absent`; `KOLLA_SKIP` skips
    the item; IPv6 keys are skipped when IPv6 is disabled (`roles/sysctl/tasks/main.yml:10-20`). The IPv6 check runs
    twice: in `roles/loadbalancer/tasks/config-host.yml:3-6` and again in the sysctl role (`roles/sysctl/tasks/main.yml:2-5`).
  - Then `module-load` with `ip_vs` (20-25). This is loaded even when `enable_keepalived` is false, because it has no
    `when`.
- **`roles/loadbalancer/tasks/check-containers.yml:2-3`.** **Changed in 2025.1:** it imports `service-check-containers`,
  which runs `compare_container` for each enabled service (`roles/service-check-containers/tasks/main.yml:4-29`) and
  then notifies `Restart <key> container` for the changed ones only (34-41). `compare_container` includes
  `kolla_set_configs --check` inside the running container (`module_utils/kolla_container_worker.py:20, :58-65`), so
  a changed file under `/etc/kolla/<service>/` is a "change" when its `config.json` lists it.

### 1.4 Config files generated (`ansible/roles/haproxy/tasks/config.yml`)

In 2025.1: `roles/loadbalancer/tasks/config.yml` (17 entries: 16 named tasks and the `copy-certs.yml` include). **Changed
in 2025.1:** no task notifies; the column "detected by" names the container whose `compare_container` sees the
change, through its `config.json` entries (1.3).

| dest (host) | source / override order | detected by |
|---|---|---|
| `/etc/kolla/{haproxy,proxysql,keepalived,haproxy-ssh}/` dirs (2-10), `/etc/kolla/haproxy/services.d/` (12-22), `proxysql/{users,rules}` (24-37), `keepalived/checks/` (39-49) | n/a | none |
| `stat` of `{{kolla_certificates_dir}}/proxysql-ca.pem` on localhost, run once (51-61, new) | n/a | none |
| removes `/etc/kolla/haproxy/services.d/mariadb.cfg` when ProxySQL is enabled (63-72) | n/a | none (a removed source file is not compared, see 1.8 (D)) |
| `/etc/kolla/keepalived/checks/check_alive_<svc>.sh` (74-105) | removed for disabled services, templated for enabled ones; both only with `keepalived_track_script_enabled` | keepalived (`/checks`) |
| `/etc/kolla/<svc>/config.json` (107-113) | `templates/<svc>/<svc>.json.j2` | the same container |
| `/etc/kolla/haproxy/haproxy.cfg` (115-127) | first_found: `{{node_custom_config}}/haproxy/<inventory_hostname>/haproxy_main.cfg` → `{{node_custom_config}}/haproxy/haproxy_main.cfg` → `haproxy/haproxy_main.cfg.j2` | haproxy |
| `/etc/kolla/proxysql/proxysql.yaml` (129-141) | same pattern under `{{node_custom_config}}/proxysql/` | proxysql |
| `/etc/kolla/haproxy/services.d/external-frontend.cfg` (143-153) | `haproxy/haproxy_external_frontend.cfg.j2`, only when `haproxy_single_external_frontend` (default `false`, `group_vars/all.yml:1067`) | haproxy |
| `/etc/kolla/haproxy/services.d/*.cfg` (155-165) | `with_fileglob: {{node_custom_config}}/haproxy/services.d/*.cfg` (operator custom frontends) | haproxy |
| `/etc/kolla/keepalived/keepalived.conf` (167-179) | first_found: `…/keepalived/<host>/keepalived.conf` → `…/keepalived/keepalived.conf` → `keepalived/keepalived.conf.j2` | keepalived |
| `include_tasks: copy-certs.yml` (181-183), only when `loadbalancer_copy_certs` (`roles/loadbalancer/defaults/main.yml:203`: any of CA copy, external, internal or backend TLS, or database TLS) | **moved in 2025.1** from `config.yml`: `haproxy.pem` from `kolla_external_fqdn_cert` (`/etc/kolla/certificates/haproxy.pem`, `group_vars/all.yml:1061`) when `kolla_enable_tls_external` and Let's Encrypt does not manage the external certificate (`roles/loadbalancer/tasks/copy-certs.yml:2-16`); `haproxy-internal.pem` from `kolla_internal_fqdn_cert` (1062), same logic for internal (18-32); new ProxySQL `proxysql-{ca,cert,key}.pem` with `database_enable_tls_internal` (34-70); then `service-cert-copy` for the CA bundle (72-77, section 7) | haproxy, proxysql; the CA bundle: every container of the role |
| `/etc/kolla/haproxy/haproxy_run.sh` (185-197), `/etc/kolla/proxysql/proxysql_run.sh` (199-211) | first_found: `…/<svc>/<host>/<svc>_run.sh` → `…/<svc>/<svc>_run.sh` → template | haproxy / proxysql |
| `/etc/kolla/haproxy-ssh/{sshd_config,id_rsa.pub}` (213-224) | templates, mode 0600, only where `haproxy-ssh` is enabled | haproxy-ssh |
| `/etc/kolla/haproxy/services.d/<service-key>.cfg` | written by **haproxy-config** (section 2) from each service role's `loadbalancer.yml` | haproxy, at the final compare (`site.yml:319-324`) |
| `/etc/kolla/haproxy/external-frontend-map` | written by **haproxy-config** with `blockinfile`, one block per service key, only with `haproxy_single_external_frontend` (`roles/haproxy-config/tasks/main.yml:23-49`) | haproxy, at the final compare |

Inside the container:
- **haproxy.json.j2.** It copies `haproxy_run.sh`, `haproxy.cfg` and the whole `services.d/` directory
  (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:2-21`). **Changed in 2025.1:** the external-frontend map is
  always listed, as `optional` unless `haproxy_single_external_frontend` is on (22-28). `haproxy.pem` and
  `haproxy-internal.pem` are listed according to `letsencrypt_managed_certs` and are `optional` when their TLS side is
  off (28-42). The PEM files go to `/etc/haproxy/certificates/`, owned by `haproxy` (31-32, 38-39), the mount point of
  the `letsencrypt_certificates` named volume (1.2). With `kolla_copy_ca_into_containers` the CA bundle is listed too
  (43-49).
  - The 2024.1 oddity is gone: `external-frontend.cfg` reads `/etc/haproxy/external-frontend-map`
    (`templates/haproxy/haproxy_external_frontend.cfg.j2:11`), and the map is now copied whenever the single frontend
    is on.
  - `kolla_set_configs --check` compares the files of a listed directory one by one, from the source side only
    (kolla `docker/base/set_configs.py:213-231`), so a file that exists only in the container's `services.d` is not
    detected.
- **haproxy_run.sh.j2.** With TLS on, when a PEM file is missing in `/etc/haproxy/certificates/`, it first writes a
  one-day self-signed certificate there (3-36). **Changed in 2025.1:** it then runs
  `exec /usr/sbin/haproxy -W -db -p /run/haproxy.pid -f /etc/haproxy/haproxy.cfg -f /etc/haproxy/services.d/` (38).
  HAProxy loads every file of the directory given to `-f`; which files it skips is upstream behaviour, NOT AVAILABLE
  here.
  - It is started in master-worker mode (`-W`), which could do a SIGUSR2 reload, but Kolla never uses that.
- **haproxy_main.cfg.j2.**
  - `nbthread {{ haproxy_threads }}`, with a fixed `cpu-map auto:1/all 0-63` when `haproxy_thread_cpu_map` is on and
    more than one thread is set (9-12; `roles/loadbalancer/defaults/main.yml:66-67`).
  - **Changed in 2025.1:** with TLS on, the `global` section renders `haproxy_ssl_settings` line by line (15-21), whose
    default profile `modern` adds `no-tlsv12` on the bind and server sides (`group_vars/all.yml:441-461`).
  - `listen stats` is on `api_interface_address:haproxy_stats_port` (1984) (37-44; `group_vars/all.yml:437`).
  - `listen metrics` on `api_interface_address:prometheus_haproxy_exporter_port` (9101) with HAProxy's built-in
    `prometheus-exporter`, when `enable_prometheus_haproxy_exporter` (46-51), which defaults to `enable_haproxy`
    (`group_vars/all.yml:670, :1330`).
  - `frontend status` (monitor-uri) is on `api_interface_address` and, when it differs, on the internal VIP, both on
    `haproxy_monitor_port` (53-59).
  - `haproxy_monitor_port: "61313"` (`group_vars/all.yml:438`).
- **keepalived.conf.j2** (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2`), unchanged since 2023.1:
  - `vrrp_script check_alive { script "/check_alive.sh" interval 2 fall 2 rise 10 }` (1-8), only while
    `keepalived_track_script_enabled` (default True, `roles/loadbalancer/defaults/main.yml:190`).
  - `state BACKUP` + `nopreempt` (11-12).
  - **`priority {{ groups['loadbalancer'].index(inventory_hostname) + 1 }}`** (15).
  - Unicast peers are built from `groups['loadbalancer']` only with `keepalived_traffic_mode == 'unicast'` (17-29). The
    VIP(s) are at 30-35. `track_interface` for the external VIP (36-40). `auth_type PASS` (41-44). `track_script
    check_alive` (45-49).
  - `keepalived_virtual_router_id: "51"` (`group_vars/all.yml:247`). `keepalived_traffic_mode: "multicast"`
    (`roles/loadbalancer/defaults/main.yml:62`).

### 1.5 Handlers (`ansible/roles/haproxy/handlers/main.yml`). Definition order = run order (see common mechanics)

**Still holds in 2025.1:** the handlers are in `roles/loadbalancer/handlers/main.yml`; the only change since 2024.1 is
`any_errors_fatal: true` on the two "wait for backup" handlers. The names that the generic check notifies
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
   notifies `Wait for backup haproxy to start` (115-119: `wait_for api_interface_address:haproxy_monitor_port`,
   **new: `any_errors_fatal: true`**).
7. **`Start backup proxysql container`** (121-148), when enabled; notifies `Wait for backup proxysql to start`
   (150-154, **new: `any_errors_fatal: true`**).
8. **`Start backup keepalived container`** (156-177): topic keepalived; notifies `Wait for virtual IP to appear`.
9. **`Stop master haproxy container`** (181-195), **`Stop master proxysql container`** (197-210, topics proxysql and
   keepalived), **`Stop master keepalived container`** (212-224, topic keepalived only).
10. **`Start master haproxy container`** (226-249) → `Wait for master haproxy to start` (251-254);
    **`Start master proxysql container`** (256-279) → `Wait for master proxysql to start` (281-284);
    **`Start master keepalived container`** (286-307) → `Wait for virtual IP to appear`.
11. **`Wait for haproxy to listen on VIP`** (309-319) and **`Wait for proxysql to listen on VIP`** (321-331):
    `wait_for kolla_internal_vip_address:<port>`, both `listen: Wait for virtual IP to appear`.
12. **`Restart haproxy-ssh container`** (333-347): a plain handler, no `listen`, no backup/master split: it restarts
    `haproxy_ssh` on every notified host at once, after the sequence above.

Every stop/start handler has `when: kolla_action != "config"`. The `wait_for` handlers set no timeout, so the module
default applies (300 s, ansible-core 2.18.20 `lib/ansible/modules/wait_for.py:483`), and only prove that a port
listens; they say nothing about the backends. **New in 2025.1:** when a backup's HAProxy or ProxySQL port does not
open within that time, `any_errors_fatal` fails every host of the play at once, so the master is never stopped
(`roles/loadbalancer/handlers/main.yml:119, :154`). [NOT AVAILABLE] that this is how it behaves on a real cloud; to
be confirmed by the community.

Other properties:
- There is no `run_once`, `delegate_to` or serial logic inside the handlers. The backup/master split is the only
  ordering: all backups of the batch stop and start in the same handler step, then the master.
- **If no host of the batch holds the VIP** (e.g. `enable_keepalived: no` with an external load balancer, or the VIP
  is on no loadbalancer host), every host is grouped as a backup and all of them stop and start haproxy at once; the
  master handlers are skipped (`groups.kolla_ha_is_master_True is defined`, 191, 242).
- With `deploy -e kolla_serial=1`, Ansible runs the whole play, handler flushes included, once per one-host batch
  (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:178-188`, `:269-313`; flush points
  `lib/ansible/playbook/play.py:327-333`). `reconfigure` and `upgrade` cannot be batched ([F19](../findings.md#f19)).
- **Changed in 2025.1:** no task notifies these topics directly any more; the only notifier is
  `service-check-containers` (`roles/service-check-containers/tasks/main.yml:34-41`), reached from the role's
  `check-containers.yml` and from the final include of the play. `haproxy-config` and `proxysql-config` no longer
  notify (`ansible/roles/haproxy-config/tasks/main.yml:2-49`, `roles/proxysql-config/tasks/main.yml:2-18`).

### 1.6 Bootstrap / DB / Keystone / RabbitMQ registration

None.

### 1.7 Dependencies

- **VIP-related variables.** `kolla_internal_vip_address`, `kolla_external_vip_address` (`group_vars/all.yml:54-56`),
  `haproxy_enable_external_vip` (1055), `kolla_external_vip_interface` and `api_interface` (299-300).
- **TLS:** `kolla_enable_tls_{internal,external}` and the cert paths (1058-1062). These are produced by the
  `certificates` playbook (section 8), supplied by the operator or by the `letsencrypt` role (`site.yml:329-341`).
- **Everything behind the VIP.** Every service's `loadbalancer.yml` (section 2) builds backend lists from
  `groups[<svc group>]` and `hostvars[host].ansible_facts.hostname`, so facts are needed for all backend hosts (handled
  by `ansible/gather-facts.yml`, including the `--limit` path).
  - `database_address: "{{ kolla_internal_fqdn }}"` (`group_vars/all.yml:89`) and `kolla_internal_fqdn` = the VIP
    (55). So **all DB traffic goes through the load balancer**, which in 2025.1 is ProxySQL by default
    (`group_vars/all.yml:554, :958`).
- **chrony.** Not a dependency: 2025.1 has no chrony role (section 4).
- **Logging.** `syslog_server: "{{ api_interface_address }}"` (`roles/loadbalancer/defaults/main.yml:58`) and
  `syslog_udp_port` (fluentd) (`group_vars/all.yml:731`). This needs fluentd from the `common` play.

### 1.8 Operationally notable behaviour

- **(A) Any detected change means a full restart of haproxy on all loadbalancer nodes, never a reload by Kolla-Ansible.**
  - A change in any one service's `services.d/<svc>.cfg`, the external-frontend map, a cert, haproxy.cfg or
    haproxy_run.sh reaches the `Restart haproxy container` topic **when a compare runs**: the role's own
    `check-containers.yml` or the final include of the play (1.3). Under `-t <service>` neither runs (1.9).
  - **Still holds in 2025.1:** the restart is staged (1.5): `haproxy` stops and starts on all backups of the batch at
    once, the play waits for their monitor port, then it stops and starts on the VIP holder. Each stop is a systemd
    stop of the unit, i.e. `<engine> stop -t 60` ([R24](../../risk/risk-register.md#r24)). While the master's haproxy is
    stopped, every API, the database (through ProxySQL on the VIP, or HAProxy) and so on that reaches the VIP holder is
    not served there.
  - Exception, since 2024.1: a Let's Encrypt renewal is loaded through the admin socket by the letsencrypt
    containers, without a Kolla-Ansible restart (common mechanics).
  - **Changed in 2025.1:** `haproxy_run.sh` now `exec`s haproxy (`roles/loadbalancer/templates/haproxy/haproxy_run.sh.j2:38`),
    so haproxy replaces bash as dumb-init's child and receives the engine's stop signal
    ([Kolla images §2.6](../../concepts/kolla-images.md#26-signals-and-pid-1)). NOT AVAILABLE: how long the outage lasts
    per run, and whether established connections are cut; a container still running after 60 s is killed.
- **(B) Whether a haproxy restart causes VIP failover or a VIP outage is NOT AVAILABLE.**
  - keepalived tracks `check_alive` with `interval 2 fall 2 rise 10`
    (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:2-7`).
  - NOT AVAILABLE: whether keepalived goes to FAULT and drops the VIP while haproxy is stopped on the VIP holder, and
    how long the VIP is then absent. The backups are already restarted at that point (1.5). The "Wait for master
    haproxy" handler checks `api_interface_address`, not the VIP (`roles/loadbalancer/handlers/main.yml:251-254`).
  - `nopreempt` is set (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:12`). Which node holds the VIP
    afterwards is NOT AVAILABLE.
  - The check itself is known: `/check_alive.sh` runs `check_alive_haproxy.sh`, which asks the haproxy stats socket
    for `show info`, and, with ProxySQL, `check_alive_proxysql.sh`, which logs in to the ProxySQL admin socket
    (section 1.2). So the check fails as soon as either stops answering. **New in 2025.1:** a wrong or changed
    `proxysql_admin_password` in the rendered check makes it fail too; what keepalived then does with the VIP is NOT
    AVAILABLE, to be confirmed by the community.
  - A keepalived change (`Restart keepalived container`) stops and starts keepalived on the backups, then stops
    haproxy, proxysql and keepalived on the VIP holder, which the handler comment describes as dropping the VIP
    (`roles/loadbalancer/handlers/main.yml:2-6, :212-224`). Where the VIP goes and for how long is NOT AVAILABLE.
- **(C) keepalived priority depends on inventory order.**
  - `priority = index in groups['loadbalancer'] + 1` (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`).
  - Inserting, removing or re-ordering a loadbalancer host changes `keepalived.conf` on every host after it in the
    list. In unicast mode it changes on all hosts (peer list, 20-27). Each changed host goes through the staged
    keepalived sequence of 1.5. Whether that moves or flaps the VIP is NOT AVAILABLE.
- **(D) Stale frontends are never removed.**
  - Nothing in the tree deletes files in `services.d`, except `mariadb.cfg` when ProxySQL is enabled
    (`roles/loadbalancer/tasks/config.yml:63-72`); `haproxy-config` only templates and adds map blocks
    (`roles/haproxy-config/tasks/main.yml:2-49`).
  - If a service is disabled (`enable_X: no`), its `include_role` is skipped (`when: enable_X`). The old
    `/etc/kolla/haproxy/services.d/X.cfg` stays and is loaded by `haproxy_run.sh` on the next restart.
  - The same is true for removed custom `node_custom_config/haproxy/services.d/*.cfg` files, for
    `external-frontend.cfg` after `haproxy_single_external_frontend` is turned off (its task is then skipped,
    `roles/loadbalancer/tasks/config.yml:151-153`), and for a disabled service's block in `external-frontend-map` (the
    `blockinfile` task runs only for enabled services, `roles/haproxy-config/tasks/main.yml:45-49`).
  - **New in 2025.1:** a removed source file is not compared (the check walks the source side only, 1.4), so the
    removal of `mariadb.cfg` by itself does not restart haproxy; the container keeps its copy until it is restarted
    for another reason, and a copy-always restart copies the directory again without deleting the old file. Whether
    the old copy then stays loaded is NOT AVAILABLE, to be confirmed by the community.
  - BUG/oddity (code fact).
- **(E) `-t haproxy` also runs `common` on haproxy hosts.** **No longer holds (since 2023.1, still in 2025.1).** No
  role has a `common` meta dependency and `common` is its own play, tagged `common` only (`site.yml:88-103`). Ansible's
  own parse lists no `common` tag in the loadbalancer play ([list-tags-site.txt](../listings/list-tags-site.txt)).
  So `kolla-ansible reconfigure -i <inventory> -t haproxy` does not touch fluentd, cron or kolla-toolbox.
- **(F) Upgrade "Stopping all slave keepalived containers".** **Does not exist in 2025.1** (gone since 2023.1).
  `roles/loadbalancer/tasks/upgrade.yml` holds two other tasks, the removal of the `prometheus_haproxy_exporter`
  container and its configuration on every loadbalancer host (4-19), then imports `deploy.yml` (21). A keepalived
  image or configuration change is applied by the staged handlers (1.5).
  - The Ussuri **Likely BUG 1** stays gone: the stop handlers pass `ignore_missing: true`
    (`roles/loadbalancer/handlers/main.yml:41, :59, :75, :186, :203, :218`), and the exporter removal uses
    `stop_and_remove_container`, which does nothing when the container is absent
    (`module_utils/kolla_docker_worker.py:444-448`).
  - The Ussuri **Likely BUG 2** stays gone: the handlers read the addresses with `ip addr show dev {{ api_interface }}`
    instead of facts (`roles/loadbalancer/handlers/main.yml:9-15`), and the precheck converts the interface name:
    `ansible_facts[kolla_external_vip_interface | replace('-', '_')]` (`roles/loadbalancer/tasks/precheck.yml:103-109`).
- **(G) Things that run on every deploy, reconfigure and upgrade:**
  - The IPv6 check (twice), sysctl and modprobe (config-host and the `sysctl` role).
  - The 17 entries of `config.yml` (directories, checks, templates, copies).
  - **Two compare passes** (the role's `check-containers.yml` and the final include): each runs `compare_container`
    for haproxy and keepalived, plus proxysql (on by default) and, with Let's Encrypt, haproxy_ssh; each compare does an
    `<engine> exec kolla_set_configs --check`.
  - Plus up to 38 service includes, each importing `loadbalancer-config` → `haproxy-config` (one template task, the
    single-frontend `blockinfile` task and one firewalld task, `roles/haproxy-config/tasks/main.yml:2-67`) and, with
    ProxySQL, `proxysql-config`.
  - On upgrade, the exporter removal (two tasks).
  - The cost scales with the number of loadbalancer hosts, not with computes.
  - The `sysctl` task with `KOLLA_UNSET` *removes* any manual `net.ipv4.tcp_retries2` line from `/etc/sysctl.conf` on
    every run (`roles/loadbalancer/tasks/config-host.yml:15`, `roles/sysctl/tasks/main.yml:10-16`).
- **(H) Non-local bind is needed.**
  - `ip_nonlocal_bind=1` is set only when `set_sysctl` is true (`roles/loadbalancer/tasks/config-host.yml:13-14,17-18`).
    Backup nodes bind VIP addresses (`roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:56`; every frontend,
    `roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:50`; the single external frontend,
    `roles/loadbalancer/templates/haproxy/haproxy_external_frontend.cfg.j2:10`).
  - NOT AVAILABLE: whether haproxy starts on non-VIP nodes with `set_sysctl: no` and no manual sysctl.
- **(I) VRRP router id collisions.** `keepalived_virtual_router_id` defaults to `51` with multicast. Two Kolla clouds on
  the same L2 segment collide unless it is changed (`group_vars/all.yml:247`,
  `roles/loadbalancer/defaults/main.yml:62`).

### 1.9 What exactly happens in the haproxy play for `-t <service>` and `-t haproxy`

How the tags combine (the mechanics, ansible-core 2.18.20):
1. **Play tags.** They are inherited by everything statically in the play: the role tasks, the `block`, and each
   `include_role` statement. A loadbalancer role task ends up with tags `{haproxy, keepalived, loadbalancer}`. `tags`
   is an extending attribute that collects the parent, role, dependency chain and play values (ansible-core 2.18.20
   `lib/ansible/playbook/taggable.py:40`, `lib/ansible/playbook/block.py:308-359`).
2. **Include tags.** The `include_role` statement for keystone has tags `{keystone, haproxy, keepalived, loadbalancer}`.
   **New in 2025.1:** the final `include_role … tasks_from: check-containers` has no tag of its own, so it carries only
   `{haproxy, keepalived, loadbalancer}` (`site.yml:319-324`).
3. **Dynamic include boundary.** `include_role` is *dynamic*. The included role's blocks get the `include_role` as
   parent (ansible-core 2.18.20 `lib/ansible/playbook/role_include.py:100,106-107`); an include is not statically
   loaded (`lib/ansible/playbook/task_include.py:48`), so `Block._get_parent_attribute` skips it and takes the
   grandparent's value (`lib/ansible/playbook/block.py:310-313`). So the tasks inside `keystone/tasks/loadbalancer.yml`
   would only carry the play tags, and would be filtered out under `-t keystone` (included blocks are filtered on
   tags, `lib/ansible/plugins/strategy/linear.py:274`).
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
   `cell_proxy_loadbalancer.yml:12`). The final `check-containers` include gets no such workaround.
5. **Handlers ignore tags.** They run whenever they are notified (see common mechanics).

**`kolla-ansible reconfigure -i <inventory> -t keystone`** (2024.1 form: `kolla-ansible -i <inventory> -t keystone
reconfigure`). From the rules above and the tag test in ansible-core 2.18.20 `lib/ansible/playbook/taggable.py:67-77`
(`always` always matches, 70-71):
- loadbalancer role tasks are **skipped**. They are tagged only with the play tags. That covers config-host,
  config.yml (haproxy.cfg, keepalived.conf, checks, pems, haproxy_run.sh, custom services.d, external-frontend.cfg,
  haproxy-ssh files) and the role's check-containers.
- Exactly **one** service `include_role` runs: keystone's (`site.yml:203-207`). It is skipped if `enable_keystone` is
  false. The other 37 service includes are skipped by tag.
- haproxy-config renders `/etc/kolla/haproxy/services.d/keystone.cfg` only (and, with the single external frontend,
  keystone's block of `external-frontend-map`), on every loadbalancer host. Only service keys that have a `haproxy:`
  dict and are enabled are rendered.
- **Changed in 2025.1: haproxy is not restarted, even if `keystone.cfg` changed.** The file task does not notify, and
  the final `check-containers` include is skipped by tag ([F18](../findings.md#f18)). The running haproxy keeps the
  old keystone frontend. The new file goes live at the next run of the play that reaches a compare: `-t haproxy`,
  `-t keepalived`, `-t loadbalancer` or no tag, or the next restart of the haproxy container for any reason.
  - Until then, `/etc/kolla/haproxy/` and the running haproxy differ, and that drift is not visible to the operator
    except through `kolla_set_configs --check` in the container.
- Cert rotation for the VIP needs `-t haproxy` (or `-t loadbalancer`). The PEM copy is a loadbalancer role task.
- `--skip-tags haproxy` skips the whole play, including all per-service includes and the final compare: each one
  carries the inherited play tag, and a task with a skipped tag does not run (ansible-core 2.18.20
  `lib/ansible/playbook/taggable.py:79-88`).
- Tag aliases:
  - `-t nova` hits both nova and nova-cell (`site.yml:252-265`).
  - `-t memcache` (alias tag of the memcached play, `site.yml:428-429`) does **not** hit memcached's include, which is
    tagged only `memcached` (`site.yml:233-237`).

**`kolla-ansible reconfigure -i <inventory> -t haproxy`** (`-t keepalived` and `-t loadbalancer` select the same play
and the same tasks: they are all play tags, `site.yml:115-118`).
- `common` does not run. The loadbalancer role runs `reconfigure.yml` → `deploy.yml`: config-host, config.yml (all
  files in 1.4), check-containers (first compare).
- **All 38** service `include_role` statements match, through the inherited play tags. Every enabled service's
  `services.d/*.cfg` is re-rendered. Then the final include runs the second compare, which sees the `services.d`
  changes.
  - `placement`'s include has **no `when`** (`site.yml:248-251`). `placement-api.cfg` is always written, and is empty
    if `enable_placement` is false (`ansible/roles/placement/defaults/main.yml:7,14`).
- End-of-play handlers: the staged sequence of 1.5 for whichever topics were notified (haproxy, keepalived,
  proxysql), backups first, then the VIP holder, then the waits; then `Restart haproxy-ssh container` if notified.
  Both compares feed the same flush, so haproxy restarts at most once per run.
- No service containers (keystone etc.) are touched.
- The `letsencrypt` play is not selected by these tags: it carries only the role tag `letsencrypt`
  (`site.yml:340-341`).

**`kolla-ansible reconfigure -i <inventory>` (no tags).** Same as `-t haproxy`, plus all the other plays. It is still a
single staged haproxy restart per run, at the end of the loadbalancer play (the fix for LP#1864810/LP#1875228,
`releasenotes/notes/bug-1864810-5a5d0f91c0171b19.yaml`; role and `tasks:` share one flush, ansible-core 2.18.20
`lib/ansible/playbook/play.py:329-331`). The restart happens only if a compare reported drift.

**`deploy-containers` and `-t <svc> deploy-containers`.** Only loadbalancer `check-containers.yml` runs, and only
under `-t haproxy`/`keepalived`/`loadbalancer` or no tags. The services.d includes and the final include do not run
(`site.yml:327`); the one compare still sees the `services.d` drift, because it compares the whole directory.

---

## 2. `haproxy-config` role

### 2.1 How it is applied

- Only through `loadbalancer-config` (`roles/loadbalancer-config/tasks/main.yml:2-4`, when `haproxy_config_install`,
  true for every project except `mariadb` with ProxySQL, `roles/loadbalancer-config/defaults/main.yml:2`), which is
  imported (with `tags: always`) from the 38 `ansible/roles/*/tasks/loadbalancer.yml` files, which are `include_role`'d by the loadbalancer play (`site.yml:121-318`).
  - Every role that has a `loadbalancer.yml` is included; a diff of the two lists is empty.
  - `letsencrypt` has a `loadbalancer.yml` and an include, but its services define no `haproxy` entry
    (`roles/letsencrypt/defaults/main.yml:2-16`), so no frontend file is written for it (2.2).
  - `nova-cell` loops over cells (`ansible/roles/nova-cell/tasks/proxy_loadbalancer.yml:5-19` →
    `cell_proxy_loadbalancer.yml:3-12`, using `namespace_haproxy_for_cell`).
- No defaults-level `_services` dict of its own. It consumes `project_services`.

### 2.2 Task (`ansible/roles/haproxy-config/tasks/main.yml:2-21`), the only task

Since 2024.1 the role has three tasks. **Changed in 2025.1:** none of them notifies a handler. The template task is `roles/haproxy-config/tasks/main.yml:2-21`, then the single-frontend map task (23-49), then the firewalld task (51-67). The block below is the 2025.1 template task.

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
```
- **Template choice.** `haproxy_service_template` defaults to `haproxy_single_service_split.cfg.j2` (frontend/backend
  split) (`roles/haproxy-config/defaults/main.yml:2`); it is the only template the role ships. Operators can override
  per service key (`<key>.cfg`), per host or globally under `/etc/kolla/config/haproxy-config/` (task lines 5-10).
- **Single external frontend (since 2024.1).** "Add configuration for {{ project_name }} when using single external frontend" (23-49) adds, with `blockinfile` and a `# BEGIN/END <service key>` marker, one line
  `<external_fqdn> <name>_back` per external, enabled HTTP entry that has a frontend, to
  `/etc/kolla/haproxy/external-frontend-map`, when `haproxy_single_external_frontend`; it no longer notifies. The split template then skips the external HTTP frontends (148-152), and the
  loadbalancer role writes the shared `external_frontend` (1.4). Every `<svc>_public_port` then becomes
  `haproxy_single_external_frontend_public_port`, 443 with external TLS, else 80 (e.g. `group_vars/all.yml:344`,
  `:1068`).
- **Firewalld.** "Configuring firewall for {{ project_name }}" opens each external service port in
  `external_api_firewalld_zone` when `enable_external_api_firewalld`, skipped for `kolla_action == "config"` (51-67).
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
  - **Since 2024.1:** TLS binds use `/etc/haproxy/certificates/haproxy.pem` and `…/haproxy-internal.pem` and add
    `alpn h2,http/1.1` when `haproxy_enable_http2` (default `yes`) (2-5; `group_vars/all.yml:1056-1057`). The redirect
    frontend now exempts `/.well-known/acme-challenge/` from the HTTPS redirect (53-56).
  - `tls_backend` adds `ssl verify required ca-file <haproxy_backend_cacert>` when `kolla_verify_tls_backend`, else
    `ssl verify none` (91-97).

### 2.3 Handler

It has none of its own. **Changed in 2025.1:** it notifies nothing either. Its files reach HAProxy only when a compare
of the `haproxy` container runs afterwards: the final `include_role … tasks_from: check-containers` of the loadbalancer
play (`site.yml:319-324`), which notifies the `Restart haproxy container` topic of the loadbalancer role's handlers
(`roles/loadbalancer/handlers/main.yml:18-21`, …) when it sees drift (1.3, 1.9).

`include_role` also *appends the included role's handlers* to the play (ansible-core 2.18.20
`lib/ansible/playbook/role_include.py:112-115`; `lib/ansible/plugins/strategy/linear.py:258`).
They are never notified here, so this is harmless.

### 2.4 Notable

- **Stale files are not removed** (see 1.8 D).
- If a service's `enabled` is false, the task is skipped and the file is left as it was. It is not emptied.
- **New in 2025.1:** a file written under `-t <service>` stays unapplied until a later run of the play reaches a
  compare (1.9).
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

`site.yml:417-429`: hosts `memcached` ∩ `enable_memcached_True`, `serial: kolla_serial`, `max_fail_percentage`
(423-426), role tags `[memcache, memcached]`. No meta dependency on `common` (no role has one in 2025.1). The default
inventory is `[memcached:children] control` (`ansible/inventory/multinode:116-117`).

### 3.2 `memcached_services` (`ansible/roles/memcached/defaults/main.yml:2-21`)

In 2025.1: `roles/memcached/defaults/main.yml:2-22`; only the image name changed since 2024.1 (it gains
`docker_image_name_prefix`, 27).

| key | container | group | enabled | flags |
|---|---|---|---|---|
| memcached | `memcached` | memcached | `true` | not privileged; volumes are only config, localtime and timezone (45-48); a `healthcheck_listen` container healthcheck (32-43) |

- **Haproxy entry.** It has a haproxy sub-entry `memcached` (tcp, port `memcached_port` 11211, `group_vars/all.yml:575`)
  with `enabled: enable_memcached and enable_haproxy_memcached` (13).
  - `enable_haproxy_memcached: "no"` by default (`group_vars/all.yml:847-850`). The comment there: clients do
    client-side hashing.
  - Its backend list uses `active_passive: true` (22): the first host is active, the others are `backup`
    (section 2.2).
- **Tunables.** `memcached_connection_limit: "5000"` and `memcached_max_memory: "256"` (MB) (54, 57).
- **Container command:** `memcached -v -l <api_interface_address> -p 11211 -c 5000 -U 0 -m 256`
  (`roles/memcached/templates/memcached.json.j2:2`), with `"config_files": []` (3).

### 3.3 Task flow

- `roles/memcached/tasks/main.yml:2` is `include_tasks "{{ kolla_action }}.yml"` (no host guard).
- **deploy** = `config.yml` + `check-containers.yml` (`roles/memcached/tasks/deploy.yml:2-4`). No flush; the handler
  runs at the end of the memcached play.
- **reconfigure** = deploy (`roles/memcached/tasks/reconfigure.yml:2`).
- **upgrade** = config + check-containers (`roles/memcached/tasks/upgrade.yml:2-4`).
- **deploy-containers** = check-containers.
- **pull** = service-images-pull.
- **stop** = service-stop.
- **precheck** = `service-precheck` + free port 11211 on `api_interface_address` when the container is absent
  (`roles/memcached/tasks/precheck.yml:2-27`).
- **check** = **new in 2025.1:** `service-check` (`roles/memcached/tasks/check.yml:2-4`).
- **config** = config.yml.
- **Changed in 2025.1:** `check-containers.yml` imports `service-check-containers`
  (`roles/memcached/tasks/check-containers.yml:2-3`), which notifies `Restart memcached container` only when
  `compare_container` reports a change (section 1.3).
- Loadbalancer part: `roles/memcached/tasks/loadbalancer.yml:2-7`, through the loadbalancer play (`site.yml:233-237`,
  tag `memcached`).

### 3.4 Config files

- **Only `/etc/kolla/memcached/config.json`** (`roles/memcached/tasks/config.yml:13-23`). **Changed in 2025.1:** it no
  longer notifies.
- No custom-override path (there is no config file).
- The directory task has no group guard (`roles/memcached/tasks/config.yml:2-11`).

### 3.5 Handlers

- `Restart memcached container` (`roles/memcached/handlers/main.yml:2-13`): `recreate_or_restart_container`.
  **Changed in 2025.1:** the `when: kolla_action != "config"` guard is gone; it is not needed, because the `config`
  action never reaches a compare.
- It runs on all memcached hosts in parallel at the end of the play.

### 3.6 Bootstrap

None.

### 3.7 Dependencies (consumers of memcached)

- **Every service builds its memcache server list from `groups['memcached']`.**
  - 27 roles loop `for host in groups['memcached']` in their templates (grep over `ansible/roles`).
  - Keystone example: `backend = oslo_cache.memcache_pool` and
    `memcache_servers = {% for host in groups['memcached'] %}…`
    (`ansible/roles/keystone/templates/keystone.conf.j2:48-51`).
  - Horizon uses memcached as the **session store** when `horizon_backend_database` is false and the `memcached`
    group is not empty (`SESSION_ENGINE = 'django.contrib.sessions.backends.cache'`,
    `ansible/roles/horizon/templates/_9998-kolla-settings.py.j2:19-22`); `horizon_backend_database` defaults to
    `false` (`group_vars/all.yml:1267`).

### 3.8 Operationally notable

- **All memcached instances restart at once.** FACT: they restart simultaneously (serial 0); the container mounts no
  data volume (`roles/memcached/defaults/main.yml:45-48`) and its command has no persistence option
  (`roles/memcached/templates/memcached.json.j2:2`).
  - NOT AVAILABLE: whether a restart therefore empties every cache at the same time, whether Horizon users are logged
    out (cache session backend), and whether the cold Keystone and keystonemiddleware token-validation caches give a
    load spike on Keystone and the DB.
  - Triggers are rare: a change of `api_interface_address`, port, memory or connection limit, or an image change on
    upgrade, plus, once, the unit-text drift after an upgrade from 2024.1 when no 2025.1 run has recreated or restarted
    the container ([F16](../findings.md#f16)).
  - **Changed in 2025.1:** a change confined to `config.json` is now detected by every compare, even after a separate
    `genconfig`: `kolla_set_configs --check` compares the `command` of the new `config.json` with the command the
    container started with (kolla `docker/base/set_configs.py:580-586`, `:656`). In 2024.1 a memcached setting changed
    by `genconfig` alone was never applied ([F14](../findings.md#f14)).
- **Adding or removing a memcached host is expensive.** It changes the `memcache_servers` of almost every service
  config, which means a restart of most API containers on the next full reconfigure. That cost sits outside this role.
- **Tag aliases differ.** `-t memcache` reconfigures the container but not its haproxy file. Only `-t memcached` does
  both. With defaults the include renders no frontend (`enable_haproxy_memcached: "no"`), so the difference is not
  visible.
- **memcached has no `common` dependency.** Not specific to memcached: in 2025.1 no role has one.

---

## 4. `chrony` role

**Does not exist in 2025.1** (gone since 2023.1). `ansible/roles/` has no `chrony` directory, `site.yml` has no chrony
play (the first service play is "Apply role common", `site.yml:88-103`), the `group_by` list has no `enable_chrony`
entry (`site.yml:20-75`), `group_vars/all.yml` has no `enable_chrony` or `external_ntp_servers`, `inventory/multinode`
has no `chrony` or `chrony-server` group, and kolla 2025.1 has no `docker/chrony` image. Kolla-Ansible deploys no time
service; host time sync is only checked by `kolla-ansible prechecks` (`roles/prechecks/tasks/timesync_checks.yml:1-47`,
see [Chrony](../../components/chrony.md)). The subsections below keep their headings so that links still resolve.

### 4.1 Play

None in 2025.1 (see above). Ussuri ran a chrony play on every host, computes included, before haproxy.

### 4.2 `chrony_services` (Ussuri; removed)

Gone: there is no chrony role, so no `chrony` container, privileged or not, and no `chrony_bindaddress`.

### 4.3 Task flow

None in 2025.1. `-t chrony` selects only the `always`-tagged plays (fact gathering and host grouping).

### 4.4 Config files (`ansible/roles/chrony/tasks/config.yml`)

None: no `/etc/kolla/chrony/` files are written. No 2025.1 task stops, removes or checks a `chrony` container or its
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

- No chrony container restarts, steps the clock or runs on computes in 2025.1: the Ussuri items (low data-plane risk,
  cost per host, dependence on the haproxy group, the VIP as internal time source) do not apply.
- NOT AVAILABLE: which time source the hosts use. The precheck only proves that a listed daemon is active and that
  `timedatectl` reports a synchronised clock at precheck time; no deploy or reconfigure task checks it again.

---

## 5. `ovn` role

**Still holds in 2025.1:** the role is split into `ovn-controller` (container `ovn_controller`) and `ovn-db`
(containers `ovn_northd`, `ovn_nb_db`, `ovn_sb_db` and, **new in 2025.1**, one `ovn_sb_db_relay_<n>` per Southbound
relay), each with its own play. The anchors below keep the Ussuri `ovn` names.

### 5.1 Play

Two plays:
- `site.yml:635-647`: hosts `ovn-controller` ∩ `enable_ovn_True`; `serial: kolla_serial`; `max_fail_percentage`
  (641-644); role tags `[ovn, ovn-controller]`.
- `site.yml:649-663`: hosts `ovn-nb-db` ∪ `ovn-northd` ∪ `ovn-sb-db`, ∩ `enable_ovn_True`; `serial: kolla_serial`;
  `max_fail_percentage` (657-660); role tags `[ovn, ovn-db]`. The new `ovn-sb-db-relay` group is not in the host
  list: the relays run on the hosts of the play that are in that group.
- `enable_ovn: "{{ enable_neutron | bool and neutron_plugin_agent == 'ovn' }}"` (`group_vars/all.yml:952`);
  **new:** `enable_ovn_sb_db_relay: "{{ enable_ovn | bool }}"` (953).
- Default inventory (`ansible/inventory/multinode:579-602`):
  - `ovn-controller` = `ovn-controller-compute` (= compute) + `ovn-controller-network` (= network).
  - `ovn-database` = control.
  - `ovn-northd`, `ovn-nb-db`, `ovn-sb-db` and, new, `ovn-sb-db-relay` are each `ovn-database`.
- So the `ovn-controller` play covers **all computes**. Both plays run after the openvswitch/ovs-dpdk plays;
  `ovn-controller` runs before `ovn-db`. **Changed in 2025.1:** `nova.yml` now runs after both, just before neutron
  (section 0).

### 5.2 `ovn_services` (Ussuri; now split)

In 2025.1: `ovn_controller_services` (`roles/ovn-controller/defaults/main.yml:2-9`) and `ovn_db_services`
(`roles/ovn-db/defaults/main.yml:2-41`).

| key | container | group | enabled | flags / volumes |
|---|---|---|---|---|
| ovn-controller | `ovn_controller` | ovn-controller | true | **`/run/openvswitch:/run/openvswitch:shared`**, kolla_logs (`roles/ovn-controller/defaults/main.yml:22-26`); not privileged |
| ovn-northd | `ovn_northd` | ovn-northd | true | **new** `environment` `OVN_NB_DB`, `OVN_SB_DB` (the SB cluster, not a relay) (`roles/ovn-db/defaults/main.yml:7-9`); config, localtime, logs (70-73) |
| ovn-nb-db | `ovn_nb_db` | ovn-nb-db | true | **new** `environment` `OVN_NB_DB` (17-18); named volume **`ovn_nb_db:/var/lib/openvswitch/ovn-nb/`** (74-78) |
| ovn-sb-db | `ovn_sb_db` | ovn-sb-db | true | **new** `environment` `OVN_SB_DB` (26-27); named volume **`ovn_sb_db:/var/lib/openvswitch/ovn-sb/`** (79-83) |
| ovn-sb-db-relay (**new**) | `ovn_sb_db_relay_<n>`, n = 1 … `ovn_sb_db_relay_count` | ovn-sb-db-relay | `enable_ovn_sb_db_relay` | `iterate: true`, `environment` `RELAY_ID` (31-41); config dir `/etc/kolla/ovn-sb-db-relay-<n>/`, localtime, logs, no data volume (84-87) |

- `ovn_remote_probe_interval: "60000"` (`roles/ovn-controller/defaults/main.yml:36`), `ovn_openflow_probe_interval: "60"`
  (38), `ovn_monitor_all: "false"` (40), `ovn_db_inactivity_probe: "60000"` (`roles/ovn-db/defaults/main.yml:103`),
  `ovn_leader_election_pause: 5` (147).
- **Relay sizing (new).** `ovn_sb_db_relay_count` = ceil(number of `ovn-controller` hosts /
  `ovn_sb_db_relay_compute_per_relay` (50)); relay `n` listens on `ovn_sb_db_relay_port_prefix` × 10 + n, i.e.
  16641, 16642, … (`group_vars/all.yml:640-642`; `roles/ovn-db/tasks/config-relay.yml:27`). Each relay connects to the
  SB cluster with an active probe of twice `ovn_db_inactivity_probe` (`roles/ovn-db/defaults/main.yml:106-108`,
  `roles/ovn-db/templates/ovsdb-relay.json.j2:2-19`).
- **Relay choice per client (new).** Every host picks one relay number with
  `range(1, count + 1) | random(seed=inventory_hostname)`, and `ovn_sb_connection` becomes the list of all
  `ovn-sb-db-relay` hosts on that one port when relays are on (`group_vars/all.yml:643-648`).

### 5.3 Task flow

- Both roles: `main.yml:2`: `include_tasks "{{ kolla_action }}.yml"`; `reconfigure.yml` and `upgrade.yml` import
  `deploy.yml`.
- **ovn-controller deploy** = `config.yml` → `check-containers.yml` → **`setup-ovs.yml`** → `meta: flush_handlers`
  (`roles/ovn-controller/tasks/deploy.yml:2-9`).
- **ovn-db deploy** = `lookup_cluster.yml` (on NB/SB hosts) → `bootstrap-initial.yml` (hosts without a DB volume) →
  `config.yml` → `check-containers.yml` → `meta: flush_handlers` → `bootstrap-db.yml` (hosts in both `ovn-nb-db` and
  `ovn-sb-db`) (`roles/ovn-db/tasks/deploy.yml:2-22`).
- **Changed in 2025.1:** both `check-containers.yml` import `service-check-containers`
  (`roles/ovn-db/tasks/check-containers.yml:2-3`); the relays, marked `iterate`, go through
  `roles/service-check-containers/tasks/iterated.yml:2-42`, which compares `ovn_sb_db_relay_<n>` for each n, stores the
  changed ones and notifies `Restart ovn-sb-db-relay container` once if any changed.
- **deploy-containers** = check-containers only (no setup-ovs, no cluster lookup or bootstrap, no explicit flush).
- **pull**/**stop** use the generic roles (`stop.yml` uses `ovn_controller_services` / `ovn_db_services`).
- **precheck**: ovn-db = free-port checks for 6641/6642 only (`roles/ovn-db/tasks/precheck.yml:2-33`); none for the
  relay ports; ovn-controller = empty. There is **no `service-precheck` group validation** in either role.
- **check** = **new in 2025.1:** `service-check` in both roles (`roles/ovn-controller/tasks/check.yml:2-4`,
  `roles/ovn-db/tasks/check.yml:2-4`). **config** = config.yml.

**`setup-ovs.yml` runs on every deploy, reconfigure and upgrade of `ovn-controller`.** **Still holds in 2025.1:** each
task runs an Ansible module inside the `kolla_toolbox` container (`kolla_toolbox` with `module_name:
openvswitch_bridge` / `openvswitch_db`, with `container_engine`), whose result, `changed` included, is the inner
module's (`library/kolla_toolbox.py:113-131,145-197`). These tasks notify nothing. The second task runs only on
`ovn-controller` hosts (49):

| task (lines) | hosts | effect |
|---|---|---|
| Create br-int bridge (2-11) | ovn-controller | `openvswitch_bridge` `br-int`, `fail_mode: secure` |
| Configure OVN in OVSDB (13-49), one loop item per key of `Open_vSwitch . external_ids` | ovn-controller | `ovn-encap-ip=<tunnel_interface_address>`, `ovn-encap-type=geneve`, `ovn-remote=<ovn_sb_connection>` (**a relay by default in 2025.1**), `ovn-remote-probe-interval`, `ovn-openflow-probe-interval`, `ovn-monitor-all` (40-45) |
| — `ovn-bridge-mappings` (46) | set on `ovn-controller-network`, or everywhere if `computes_need_external_bridge` (`group_vars/all.yml:1224`); **removed** elsewhere | `<physnet>:<bridge>,…`; **changed in 2025.1:** the physnet names come from `neutron_physical_networks` (`group_vars/all.yml:1215`, default `physnet1`, `physnet2`, … as before) (16) |
| — `ovn-chassis-mac-mappings` (47) | set on `ovn-controller-compute`, removed elsewhere | `<physnet>:<random_mac seeded by host+bridge>` (18) |
| — `ovn-cms-options` (48) | set on `ovn-controller-network`, **removed** elsewhere | `enable-chassis-as-gw`, plus `,availability-zones=…` when `neutron_ovn_availability_zones` is set (19-26). **Changed in 2025.1:** the zones are joined with `:` instead of `,` (24). This **overwrites** the whole value. |

### 5.4 Config files

`config.json` per service (`roles/ovn-controller/tasks/config.yml:12-18`, `roles/ovn-db/tasks/config.yml:13-20`).
**Changed in 2025.1:** no config task notifies. The NB, SB, northd and controller `config.json` files have a `command`
and a `permissions` entry for the log directory, but no `config_files`
(`roles/ovn-db/templates/ovn-nb-db.json.j2:1-10`, `roles/ovn-controller/templates/ovn-controller.json.j2:1-10`).
**New:** each relay gets `/etc/kolla/ovn-sb-db-relay-<n>/config.json` and `ovsdb-relay.json`
(`roles/ovn-db/tasks/config.yml:22-25`, `roles/ovn-db/tasks/config-relay.yml:2-32`); the relay's `config.json` copies
`ovsdb-relay.json` to `/etc/ovn/ovsdb-relay.json` (`roles/ovn-db/templates/ovn-sb-db-relay.json.j2:2-10`). The relay
tasks have no host check of their own: they run on every host of the `ovn-db` play. Apart from the relay file, the
entire configuration is on the command line:
- **ovn-nb-db and ovn-sb-db** (`roles/ovn-db/templates/ovn-nb-db.json.j2:2`, `ovn-sb-db.json.j2:2`), commands from
  `ovn_nb_command`/`ovn_sb_command` (`roles/ovn-db/defaults/main.yml:120-137`):
  - `/usr/share/ovn/scripts/ovn-ctl run_nb_ovsdb --db-nb-addr=<api ip> --db-nb-cluster-local-addr=<api ip> <bootstrap args> …`.
  - The bootstrap args are set only by `bootstrap-initial.yml` (section 5.6). For a new cluster, every host except
    `groups['ovn-nb-db'][0]` gets `--db-nb-cluster-remote-addr=<api ip of groups['ovn-nb-db'][0]>`
    (`roles/ovn-db/tasks/bootstrap-initial.yml:5-13`); a member re-created on an existing cluster points at the
    current leader (59-67).
  - The client listener is set after the flush by `ovn-nbctl … set-connection ptcp:<6641>:0.0.0.0`
    (SB: `ovn-sbctl … ptcp:<6642>:0.0.0.0`) on the cluster leader (`roles/ovn-db/tasks/bootstrap-db.yml:21-35, :46-60`).
    Plaintext TCP, no SSL, on all IPv4 addresses. Each `set-connection` is retried up to 3 times, 5 s apart (32-34,
    57-59); **changed in 2025.1:** it now talks to the local socket explicitly (`--db unix:/var/run/ovn/ovnnb_db.sock`,
    28; SB 53).
- **ovn-sb-db-relay (new)** (`roles/ovn-db/defaults/main.yml:138-145`): `ovn-ctl run_sb_relay_ovsdb` with the
  relay config file; on Debian, the remote and listener are passed on the command line instead (111-117).
- **ovn-northd** (`roles/ovn-db/templates/ovn-northd.json.j2:2`):
  `--ovnnb-db={{ ovn_nb_connection }} --ovnsb-db={{ ovn_sb_connection_no_relay }}`.
  - Those are lists of all DB hosts (`group_vars/all.yml:645, :647`); northd never uses a relay.
- **ovn-controller** (`roles/ovn-controller/templates/ovn-controller.json.j2:2`):
  `ovn-controller … tcp:127.0.0.1:{{ ovsdb_port }}`, i.e. the local OVSDB on 6640 (`group_vars/all.yml:650`). The SB
  remote comes from `external_ids:ovn-remote` set by setup-ovs.

### 5.5 Handlers (`ansible/roles/ovn/handlers/main.yml`), in definition order

`roles/ovn-db/handlers/main.yml` and `roles/ovn-controller/handlers/main.yml`. **Changed in 2025.1:** a relay handler
is new, the DB handlers pass the new `environment`, and none has a `when: kolla_action != "config"` guard any more.

1. `Restart ovn-nb-db container` (ovn-db 2-14): `recreate_or_restart_container`.
2. `Restart ovn-sb-db container` (ovn-db 16-28).
3. **New:** `Restart ovn-sb-db-relay container` (ovn-db 30-46): loops over the changed relay numbers only.
4. `Restart ovn-northd container` (ovn-db 48-60).
5. `Restart ovn-controller container` (ovn-controller 2-13), in its own play.

There are no `Wait for ovn-nb-db` / `Wait for ovn-sb-db` handlers. The `wait_for api_interface_address:6641/6642`
(timeout 60, `until success retries 10 delay 6`) and, **new**, one wait per relay port run as tasks at the end of
`bootstrap-db.yml` (62-98), after the flush, on hosts in both DB groups.

There is no `run_once`, `serial` or rolling logic.
- **All NB members restart in the same step, then all SB members, then the changed relays, then all northd.**
- The waits check only that the local TCP port is open. They do not check RAFT membership or leadership.

### 5.6 Bootstrap / registration

- No Keystone, MariaDB or RabbitMQ registration.
- **Cluster lookup** (`roles/ovn-db/tasks/lookup_cluster.yml`), on every deploy, reconfigure and upgrade: groups hosts
  by whether their `ovn_nb_db`/`ovn_sb_db` volume exists (2-20; **changed in 2025.1:** through
  `kolla_container_facts` with `action: get_volumes`); on hosts that have it, fails the play (`any_errors_fatal`, 80,
  133) when not every `ovn-nb-db`/`ovn-sb-db` host is in the current batch (33-43, 86-96), probes the port, asks each
  live member whether it is leader, and fails if the cluster exists with followers but no leader (45-79, 98-132).
- **Cluster creation and member bootstrap** (`roles/ovn-db/tasks/bootstrap-initial.yml`), only on hosts without a
  volume: on an existing cluster, an old member with the same IP is removed with `cluster/kick` on the leader
  (15-57); the bootstrap args are set (5-13, 59-67); config, check-containers and a flush start the containers
  (69-74); `bootstrap-db.yml` runs (76); the args are unset (78-81). The block is `any_errors_fatal` (83).
- **`bootstrap-db.yml`** (`roles/ovn-db/tasks/deploy.yml:19-22`): when a cluster existed, a pause of
  `ovn_leader_election_pause` seconds (7-10); then `set-connection` on the NB and SB leaders (12-60), with no
  `changed_when`, so it reports *changed* on every run on the leader; then the port waits (62-98).
- **Chassis registration** (`setup-ovs.yml`) **re-runs on every deploy, reconfigure and upgrade** of `ovn-controller`.

### 5.7 Dependencies

- **openvswitch role.** setup-ovs does not exec into `openvswitch_vswitchd`; it needs the `kolla_toolbox` container
  (from the `common` play) and an OVSDB on the host's `/run/openvswitch`. `kolla_toolbox` mounts `/run/:/run/:shared`
  with Docker, and `/run/` without `:shared` plus the `run_default_volumes_podman` sub-mounts
  (`/run/openvswitch:/run/openvswitch:shared` among them) with Podman (`roles/common/defaults/main.yml:22,103`;
  `group_vars/all.yml:174-181`). `ovn_controller` itself connects to the local OVSDB on TCP 6640, which
  `ovsdb-server` listens on (**changed in 2025.1:** set in the container command,
  `ansible/roles/openvswitch/templates/openvswitch-db-server.json.j2:2`).
- **neutron and Octavia.** `ml2_conf.ini.j2:39-40` (neutron-server) and Octavia's `octavia.conf.j2:32-33` use
  `ovn_nb_connection` and `ovn_sb_connection_no_relay`; `ovn_agent.ini.j2:2-3` and
  `neutron_ovn_metadata_agent.ini.j2:17-18` use `ovn_sb_connection`, i.e. a relay (paths under `ansible/roles/neutron/templates/`
  and `ansible/roles/octavia/templates/`).
  - Adding or removing a DB host therefore also needs a neutron reconfigure, and it changes the ovn-northd command
    line (restart on all northd hosts), the relay configuration and `ovn-remote` on every chassis.
  - **New in 2025.1:** adding the 51st `ovn-controller` host raises `ovn_sb_db_relay_count` to 2
    (`group_vars/all.yml:640`), which creates a second relay and changes the seeded relay choice, and so
    `ovn-remote`, of part of the existing chassis and agents. What the chassis do when `ovn-remote` changes is NOT
    AVAILABLE, to be confirmed by the community.
- **Shared variables.** `neutron_bridge_name` and `neutron_physical_networks` (`group_vars/all.yml:1214-1215`),
  `tunnel_interface_address` (325), `computes_need_external_bridge` (1224), `neutron_ovn_availability_zones` (1242).

### 5.8 Operationally notable

- **(A) The whole DB cluster restarts at once.** Any change to `ovn-nb-db`/`ovn-sb-db` restarts every member at once
  under serial 0 (`roles/ovn-db/handlers/main.yml:2-28`). That covers the command line (the IP or the bootstrap args),
  an image change on upgrade, the unit-text drift after an upgrade from 2024.1 ([F16](../findings.md#f16)) and,
  **new in 2025.1**, the `environment` the DB containers and northd gain, which `compare_container` compares
  (`roles/service-check-containers/tasks/main.yml:19`): on the first 2025.1 run, every NB, SB and northd container is
  expected to restart. [NOT AVAILABLE] that it does on a real cloud; to be confirmed by the community.
  - NOT AVAILABLE: whether RAFT loses quorum, how the neutron-server OVN driver, the relays and ovn-northd reconnect,
    and whether the data plane keeps its installed flows while the SB is unreachable.
  - `deploy -e kolla_serial=N` (or a `--limit`) is not a mitigation on an existing cluster: when the batch holds a DB
    host that has its volume but not every `ovn-nb-db` (or `ovn-sb-db`) host, `lookup_cluster.yml` fails the play
    (`roles/ovn-db/tasks/lookup_cluster.yml:33-43, :86-96`); `reconfigure` and `upgrade` cannot be batched at all
    ([F19](../findings.md#f19)).
- **(B) Whether the seed host is a single point of failure for re-deploys is NOT AVAILABLE.**
  - The first host is the seed only for a new cluster (no member has a volume and no leader is found,
    `roles/ovn-db/tasks/bootstrap-initial.yml:5-13`). A member whose volume was lost is re-bootstrapped against the
    current leader, after its old entry is kicked (35-67). There is still no code for backups (grep: no
    `ovsdb-client backup` in `ansible/roles`).
  - NOT AVAILABLE: what happens when every volume is lost, or when no live member reports itself leader (the play
    then fails, `roles/ovn-db/tasks/lookup_cluster.yml:74-79, :127-132`).
- **(C) ovn-controller restarts.** They happen on image or container-parameter change (upgrade, `deploy-containers`),
  on the one-time unit-text drift, or when its `config.json` command changes, and hit **all computes and network
  nodes in parallel**. **Changed in 2025.1:** a command-line change written by `genconfig` is now detected by the next
  compare, because `kolla_set_configs --check` compares the `command` of `config.json` with the running one (kolla
  `docker/base/set_configs.py:580-586`, `:656`); in 2024.1 it was never applied until the container restarted for
  another reason ([Kolla images
  §3](../../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
  - NOT AVAILABLE: whether this OVN release clears and re-installs OpenFlow flows on restart, and so whether there is
    a short data-plane interruption per chassis, plus north-south traffic loss when all gateway chassis (network nodes)
    restart together.
  - NOT AVAILABLE: whether there is also an SB reconnect storm whose size scales with the number of computes; the
    relays (one per 50 chassis) are meant to absorb it, which is also NOT AVAILABLE from the code.
- **(D) Bootstrap cost scales with computes.** Each ovn-controller host runs 2 tasks, i.e. 10 `kolla_toolbox` module
  invocations (1 bridge + 9 `external_ids` keys, `roles/ovn-controller/tasks/setup-ovs.yml:2-49`), on every deploy,
  reconfigure and upgrade, each an `exec` of `ansible localhost -m <module>` in the `kolla_toolbox` container
  (`library/kolla_toolbox.py:113-131,163-165`).
  - NOT AVAILABLE: whether the `openvswitch_db`/`openvswitch_bridge` modules report changed on an unchanged host, and
    whether a changed `ovn_sb_connection` makes every chassis reconnect.
- **(E) Gateway options are clobbered.**
  - `ovn-cms-options` is *overwritten* on network nodes with `enable-chassis-as-gw` (plus `availability-zones=` from
    `neutron_ovn_availability_zones`) and *removed* on every other ovn-controller host, on every run
    (`roles/ovn-controller/tasks/setup-ovs.yml:19-26, :48`).
  - Any manual `ovn-cms-options` value, such as availability-zone hints, is overwritten or removed on every
    deploy/reconfigure (the code above); zones belong in `neutron_ovn_availability_zones`. The impact of losing a
    manual value is NOT AVAILABLE.
  - **Changed in 2025.1:** with more than one zone, the value changes from `a,b` to `a:b` on the first 2025.1 run
    (24). How Neutron reads the new value is NOT AVAILABLE, to be confirmed by the community.
  - Bridge mappings are removed (`state: absent`) on hosts that are neither network nodes nor covered by
    `computes_need_external_bridge` (46).
- **(F) Security.** NB and SB clients and the relays connect over plain TCP (`ovn_nb_connection`,
  `ovn_sb_connection_no_relay` and `ovn_sb_connection_relay` use `tcp:`, `group_vars/all.yml:645-648`), the DB
  listener is `ptcp:<port>:0.0.0.0` (`roles/ovn-db/tasks/bootstrap-db.yml:30, :55`), and a relay listens on
  `ptcp:<port>:<api address>` (`roles/ovn-db/templates/ovsdb-relay.json.j2:4`).
- **(G) OVN + DPDK cannot work in this release (inference from code):**
  - With `enable_ovs_dpdk` the openvswitch play is skipped (`site.yml:609,618`).
  - ovs-dpdk containers are only enabled when `neutron_plugin_agent in ['openvswitch']`
    (`ansible/roles/ovs-dpdk/defaults/main.yml:10,24`), and OVN requires `neutron_plugin_agent == 'ovn'`
    (`group_vars/all.yml:952`).
  - So with OVN and `enable_ovs_dpdk`, Kolla-Ansible deploys no Open vSwitch container at all, while setup-ovs and
    `ovn_controller` need an OVSDB (5.7). Whether OVN works with an OVSDB provided outside Kolla-Ansible is NOT
    AVAILABLE.
- **(H) Missing inventory groups are not caught.** There is no group validation precheck in either role. An old
  inventory without the `ovn-*` groups only surfaces as Jinja errors on `groups['ovn-…']`. **New in 2025.1:** an
  inventory carried over from 2024.1 has no `ovn-sb-db-relay` group, while `enable_ovn_sb_db_relay` is on by default;
  what the first run then does is NOT AVAILABLE from the code beyond those Jinja lookups.
- **(I) Upgrade order, new in 2025.1.** The `ovn-controller` play (`site.yml:635`) runs before the `ovn-db` play
  (`site.yml:649`). On the first 2025.1 run, setup-ovs sets `ovn-remote` to a relay on every chassis before the
  `ovn-db` play has created the relays. How long the chassis stay without a Southbound connection, and what that does
  to the data plane, is NOT AVAILABLE, to be confirmed by the community. Setting `enable_ovn_sb_db_relay: no` for
  the upgrade run keeps the 2024.1 connection.

---

## 6. `ovs-dpdk` role

### 6.1 Play

`site.yml:620-633`: hosts `openvswitch` ∩ `enable_openvswitch_True_enable_ovs_dpdk_True`, `serial: kolla_serial`,
`max_fail_percentage` (626-629), role tag `ovs-dpdk`.
- `enable_ovs_dpdk: "no"` (`group_vars/all.yml:954`).
- The openvswitch play is mutually exclusive with it (`site.yml:605-618`).
- Default `openvswitch` group = network, compute, manila-share (`inventory/multinode:105-108`).
- No `meta/` directory (no `common` dependency).

### 6.2 `ovsdpdk_services` (`ansible/roles/ovs-dpdk/defaults/main.yml:6-35`)

Unchanged since 2023.1, except the image names, which gain `docker_image_name_prefix` (63, 67).

| key | container | mapping | enabled | flags / volumes |
|---|---|---|---|---|
| ovsdpdk-db | `ovsdpdk_db` | `host_in_groups`: compute, manila-share (if enabled), neutron-dhcp-agent, -l3-agent, -metadata-agent (11-18) | `neutron_plugin_agent in ['openvswitch']` | `/run/openvswitch:shared`, named volume `ovsdpdk_db:/var/lib/openvswitch/` (71-77) |
| ovsdpdk-vswitchd | `ovsdpdk_vswitchd` | same expression (26-33) | same | **privileged: True**; **`/lib/modules:ro`, `/run/openvswitch:shared`, `/dev:/dev:shared`** (78-85) |

- Container commands: `start-ovsdb-server 127.0.0.1` and `ovs-vswitchd unix:/run/openvswitch/db.sock … --mlockall`
  (`roles/ovs-dpdk/templates/*.json.j2`).
- `neutron_bridge_name` is set in `group_vars/all.yml:1214`: `br_dpdk` when `enable_ovs_dpdk` (else `br-ex`, or
  `br-dvs` for vmware_dvs); the role has no default of its own.
- **Changed in 2025.1, mappings:** `ovs_bridge_mappings` takes the physical network names from `neutron_physical_networks` (`group_vars/all.yml:1215`, default `physnet1`, `physnet2`, … as before), and `ovs_port_mappings` is built with `zip` instead of an index loop; for the default values the result is the same (41, 43).
- **Templating bug in `ovs_cidr_mappings`** (46), unchanged. For multiple bridges it emits the literal text
  `{neutron_bridge_name.split(',')[0]}` (single braces) instead of a Jinja expression.

### 6.3 Task flow

- **deploy** = `config.yml` → `check-containers.yml` → `meta: flush_handlers` (`roles/ovs-dpdk/tasks/deploy.yml:2-7`).
- **reconfigure** and **upgrade** = deploy.
- **deploy-containers** = check-containers.
- **precheck** = service-precheck (`roles/ovs-dpdk/tasks/precheck.yml:2-6`).
- **check** = **new in 2025.1:** `service-check` (`roles/ovs-dpdk/tasks/check.yml:2-4`).
- **Changed in 2025.1:** `check-containers.yml` imports `service-check-containers` (`roles/ovs-dpdk/tasks/check-containers.yml:2-3`), which notifies the restart handler of a changed container only.
- **config (genconfig)** = **config.yml**. This *includes host-mutating NIC binding* (see below).
- **pull.** Works: `roles/ovs-dpdk/vars/main.yml:4` sets `kolla_role_name: "ovsdpdk"`, and `service-images-pull`
  looks up `(kolla_role_name | default(project_name)) + '_services'`, i.e. `ovsdpdk_services`
  (`ansible/roles/service-images-pull/tasks/main.yml:2,14`).
- **stop** = service-stop with `ovsdpdk_services` (works).

`config.yml` key tasks (all of them run on deploy, reconfigure, upgrade **and genconfig**):
- **Config dirs and config.json** (2-18), gated by `select_services_enabled_and_mapped_to_host`; **changed in 2025.1:** the `config.json` copy no longer notifies.
- **"Copying ovs-dpdkctl tool"** (20-25). `copy src: ovs-dpdkctl.sh` (`roles/ovs-dpdk/files/ovs-dpdkctl.sh`), with
  `become` and **no `when`**.
- **"Install ovs-dpdkctl service and config"** (27-38). `command: ovs-dpdkctl.sh install`, which always reports
  changed and has no `when`. Inside `roles/ovs-dpdk/files/ovs-dpdkctl.sh` (`install`, 350-367):
  - `gen_config` runs **only if the conf file does not exist** (351-353). Later changes to bridge, port or cidr mappings
    in globals are **silently ignored**.
  - `modprobe` of the DPDK driver when it is not loaded, and persistence in `/etc/modules-load.d` or `/etc/modules`
    (`configure_kernel_modules`, 330-338).
  - Install and enable the `ovs-dpdkctl` systemd unit when its file is absent (355-357; `install_service`, 270-318),
    then `systemctl start ovs-dpdkctl` (362).
  - Rewrite the ifcfg or interfaces file for the bridge every run, and on RedHat start `ovs-dpdk-bridge`
    (`ovs-dpdkctl.sh:218-258, 363-366`).
- **"Binds the interface to the target driver specified in the config"** (40-51). `ovs-dpdkctl.sh bind_nics` unbinds and rebinds the NICs listed in `port_mappings` when their current driver
  differs (`roles/ovs-dpdk/files/ovs-dpdkctl.sh:116-127`).
  - **This runs even under `kolla-ansible genconfig`.**
- **Since 2024.1, DPDK allow-list flag:** a generated configuration now lists the DPDK NICs with `-a <pci>`
  instead of `-w <pci>` (`ovs-dpdkctl.sh:45-56`); the value is stored in the conf file when it is generated (97) and
  read by `init` into `other_config:dpdk-extra` (171). Because the conf file is never regenerated, a host whose `ovs-dpdkctl.conf` was written by 2023.1 keeps `-w`. Whether the DPDK of the 2025.1 images accepts `-w` is NOT AVAILABLE. `ovs-dpdkctl.sh` is unchanged since 2024.1.

### 6.4 Config files

- `/etc/kolla/ovsdpdk-{db,vswitchd}/config.json`; a change is seen by the compare (the `command` check, kolla `docker/base/set_configs.py:580-586`).
- `/etc/kolla/ovsdpdk-db/ovs-dpdkctl.sh` and `/etc/kolla/ovsdpdk-db/ovs-dpdkctl.conf` (generated once).
- Systemd units `/etc/systemd/system/ovs-dpdkctl.service` and `ovs-dpdk-bridge.service`, plus the network ifcfg or
  interfaces file. These notify no handler.
- There are no custom-override paths.

### 6.5 Handlers (`ansible/roles/ovs-dpdk/handlers/main.yml`), in definition order

**Changed in 2025.1:** the two restart handlers lost their `when: kolla_action != "config"` guard; nothing else
changed.

1. `Restart ovsdpdk-db container` (2-20). It **notifies 6 handlers** (14-20): wait db, bridges indexed, **Restart
   vswitchd**, bridges named, `Wait for dpdk tunnel ip`, `OVS-DPDK gather facts`.
   - Since 2024.1 the notify is spelled `Wait for dpdk tunnel ip` (19), exactly the handler's name (84). ansible-core
     2.18 matches the name exactly (ansible-core 2.18.20 `lib/ansible/plugins/strategy/__init__.py:545-552`), so the
     notify reaches the handler, and no "handler not found" error is raised
     (`lib/ansible/plugins/strategy/__init__.py:666-674`; `lib/ansible/config/base.yml:1324-1331`; kolla-ansible ships
     no `ansible.cfg`).
2. `Waiting the ovs db service to be ready` (22-32). `<engine> exec ovsdpdk_db ovs-vsctl --no-wait show`, retries 30
   delay 2.
3. `Ensuring ovsdpdk bridges are properly setup indexed` (34-50). `ovs-dpdkctl.sh init`, only if
   `ovs_physical_port_policy == 'indexed'`.
4. `Restart ovsdpdk-vswitchd container` (52-64).
5. `Ensuring ovsdpdk bridges are properly setup named` (66-82). `init`, when the policy is `named` (the default,
   `roles/ovs-dpdk/defaults/main.yml:56`).
6. **`Wait for dpdk tunnel ip`** (84-88). `wait_for: host: <dpdk_tunnel_interface_address> timeout: 300 sleep: 5`, with
   **no port and no path**, and no `when`.
   - `wait_for` then just does `time.sleep(timeout)` (ansible-core 2.18.20 `lib/ansible/modules/wait_for.py:542-543`).
   - So **every `ovsdpdk-db` restart costs a fixed 300 s sleep**, on every DPDK host of the batch in parallel,
     before the play moves on (since 2024.1).
7. `OVS-DPDK gather facts` (90-98). `setup` re-gathers facts.

### 6.6 Bootstrap

OVS DB init (`ovs-dpdkctl.sh init`: `other_config:dpdk-*`, bridges, DPDK ports,
`roles/ovs-dpdk/files/ovs-dpdkctl.sh:164-216`) runs **only
from handlers**, i.e. when `ovsdpdk-db` restarts. It is not re-asserted on a plain reconfigure.

### 6.7 Dependencies

- neutron (openvswitch agent with `ovs_datapath: netdev`, `group_vars/all.yml:970`).
- Hugepages (`ovs_hugepage_mountpoint`, `roles/ovs-dpdk/defaults/main.yml:49`).
- `dpdk_tunnel_interface` (defaults to `neutron_external_interface`, `group_vars/all.yml:306`) and its address (327).
- `neutron_plugin_agent == 'openvswitch'`.

### 6.8 Operationally notable

- **Any `ovsdpdk-db` restart also restarts `ovs-vswitchd`.** That means an image change, config.json drift or the
  one-time unit-text drift after an upgrade from 2024.1 ([F16](../findings.md#f16)).
  - NOT AVAILABLE: whether this is a data-plane outage for all VMs on that host (vhost-user reconnect).
  - It happens **on all DPDK computes in parallel**, and is followed by the **300 s sleep** of 6.5.
- **NIC rebinding and unit installation run on every deploy, reconfigure, upgrade and genconfig.** They are idempotent
  only as long as the driver already matches.
- **Sticky configuration.** `ovs-dpdkctl.conf` is never regenerated, so mapping changes, and the new `-a` flag, require
  deleting it manually.

---

## 7. `service-cert-copy` role

### 7.1 How it is applied

- `import_role: service-cert-copy` from `<role>/tasks/copy-certs.yml` in 40 roles (aodh … zun, plus `common`,
  `loadbalancer` and `letsencrypt`).
- Usually the include is gated by `<role>_copy_certs`, e.g. `keystone_copy_certs` = `kolla_copy_ca_into_containers` or
  `keystone_enable_tls_backend` (`ansible/roles/keystone/tasks/config.yml:38-40`,
  `ansible/roles/keystone/defaults/main.yml:256`).
- **loadbalancer gates on `loadbalancer_copy_certs`** (`roles/loadbalancer/tasks/config.yml:181-183`,
  `roles/loadbalancer/defaults/main.yml:203`), and imports the role with `project_name: mariadb`
  (`roles/loadbalancer/tasks/copy-certs.yml:72-77`), so its backend files are the `mariadb-*.pem` ones.
- memcached, ovn-controller, ovn-db and ovs-dpdk do **not** use it.

### 7.2 Tasks (`ansible/roles/service-cert-copy/tasks/main.yml`)

**Changed in 2025.1:** no task notifies, and the backend files follow a new gate.

| task (lines) | dest | when |
|---|---|---|
| Copy extra CA certs (2-10) | `/etc/kolla/<item.key>/ca-certificates` from `{{kolla_certificates_dir}}/ca/` | `kolla_copy_ca_into_containers` |
| Backend TLS cert (12-28) | `/etc/kolla/<item.key>/<project_name>-cert.pem`. first_found: `certificates/<host>/<project>-cert.pem` → `certificates/<host>-cert.pem` → `certificates/<project>-cert.pem` → `kolla_tls_backend_cert` | **new:** `kolla_copy_backend_tls_files` (`<role>_enable_tls_backend`, `roles/service-cert-copy/defaults/main.yml:4`) and the host is in `tls-backend` (26-27); the 2024.1 test on the service's haproxy entries and on `kolla_externally_managed_cert` is gone |
| Backend TLS key (30-46) | `…/<project_name>-key.pem` (mode 0600), with the same lookup order for `-key.pem` | same |

The loop is `with_dict: project_services | select_services_enabled_and_mapped_to_host`
(`kolla_ansible/filters.py:100-109`). The copied files reach a container only when its `config.json` lists them; the
compare then sees the change (section 1.3).

### 7.3 Notable

- **For the loadbalancer role, the loop includes `keepalived`** (and `proxysql`, and with Let's Encrypt
  `haproxy-ssh`, when enabled).
  - **Changed in 2025.1:** every `config.json` of the role now lists the CA bundle when `kolla_copy_ca_into_containers`
    is on (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:43-49`,
    `roles/loadbalancer/templates/keepalived/keepalived.json.j2:15-21`, and the proxysql and haproxy-ssh files). A
    CA bundle change (e.g. a root CA rotation) is therefore detected for haproxy **and keepalived**, which gives the
    staged sequence of 1.5 with keepalived, i.e. backups first, then haproxy, proxysql and keepalived stopped on the
    VIP holder (`roles/loadbalancer/handlers/main.yml:36-49, :156-177, :212-224, :286-307`), and, with Let's Encrypt,
    `Restart haproxy-ssh container` on every host at once (`:333-347`).
  - Whether that moves or flaps the VIP is NOT AVAILABLE.
  - The kolla image installs the bundle: keepalived starts through `kolla_start`, which runs `kolla_copy_cacerts` at
    every start. That script deletes the old `kolla-customca-*` entries and installs every file of the CA directory
    (kolla `docker/base/start.sh:16`, `docker/base/copy_cacerts.sh:6-27`;
    [Kolla images §2.4](../../concepts/kolla-images.md#24-kolla_copy_cacerts-and-kolla_httpd_setup)).
- **A CA or backend cert rotation restarts every container of every service using it** (whole fleet,
  per-play parallel), at the next run that reaches each role's compare.
- It is a pure file copy, with no expiry check.

---

## 8. `certificates.yml` playbook / `certificates` role

### 8.1 Play

`ansible/certificates.yml:1-10`:
- `import_playbook: gather-facts.yml` when `kolla_enable_tls_backend`, `rabbitmq_enable_tls` or
  `certificates_generate_libvirt` (2-6) (to obtain the API IPs of `tls-backend` hosts).
- Then `hosts: localhost`, `roles: [certificates]` (7-10).
- No serial, no tags, no `become`, no `max_fail_percentage`. It runs from `kolla-ansible certificates`
  (`kolla_ansible/cli/commands.py:187-195`).
- The docs call it a "private test Certificate Authority" (`doc/source/admin/tls.rst:68-69`).

### 8.2 Flow (`ansible/roles/certificates/tasks/main.yml:2-6`)

In 2025.1 `roles/certificates/tasks/main.yml:2-8`: `generate-root.yml` → `generate.yml` → `generate-backend.yml`
(when `kolla_enable_tls_backend`, `rabbitmq_enable_tls` or, **new**, `database_enable_tls_backend`) →
`generate-libvirt.yml` (when `certificates_generate_libvirt`, default `libvirt_tls`,
`roles/certificates/defaults/main.yml:9`).
- **Root CA** (`generate-root.yml`).
  - `root.key` RSA 4096 and `root.crt`, CN=KollaTestCA, **1024 days**, each guarded by `creates:` (14-33).
  - The CA is copied to `{{kolla_certificates_dir}}/ca/root.crt` (41-45). That is the source that
    `service-cert-copy` distributes.
- **External and internal certs** (`generate.yml`).
  - Key, CSR and cert with **365 days**, each `creates:`-guarded; the certs are signed with the `v3_req` extensions of
    the generated config.
  - They are assembled into `kolla_external_fqdn_cert` and `kolla_internal_fqdn_cert` (14-75, 113-175).
  - The internal cert is a copy of the external one when both TLS flags are on and the VIPs are the same (100-111).
  - **Changed in 2025.1:** the blocks follow `letsencrypt_managed_certs` instead of `enable_letsencrypt` (62-64, 72-74,
    161-164, 172-175), and the external or internal key pair is also generated for database internal TLS, copied to
    `proxysql-ca.pem`, `proxysql-cert.pem` and `proxysql-key.pem` (77-98, 177-191).
  - SAN: the VIP address as `IP.1`, plus the FQDN as `DNS.1` when it differs from the VIP
    (`roles/certificates/templates/openssl-kolla.cnf.j2:15-19`, same in `openssl-kolla-internal.cnf.j2`).
- **Backend cert** (`generate-backend.yml`).
  - One shared cert (**500 days**) whose SANs are the API IPs of **all `tls-backend` hosts**
    (`roles/certificates/templates/openssl-kolla-backend.cnf.j2:15-18`). The example inventory's `tls-backend` group is
    `control` and `network` (`ansible/inventory/multinode:42-44`).
  - Copied to `backend-cert.pem` and `backend-key.pem` (56-66), with `rabbitmq_enable_tls` to
    `rabbitmq-cert.pem`/`rabbitmq-key.pem` (68-79) and, **new**, with `database_enable_tls_backend` to
    `mariadb-cert.pem`/`mariadb-key.pem` (81-93).
- Global paths: `kolla_certificates_dir: "{{ node_config }}/certificates"` (`group_vars/all.yml:1060`, normally
  `/etc/kolla/certificates`).

### 8.3 Notable

- **No rotation or renewal.** Every generating step is `creates:`-guarded, so re-running never renews expired
  certificates. External and internal certs expire after 365 days; the files must be deleted manually. (Let's Encrypt
  is a separate role, not this playbook.)
- **Adding a `tls-backend` host does not update the backend SANs.** `backend.csr` and `backend.crt` exist
  (`roles/certificates/tasks/generate-backend.yml:32,48`), so the cert is not re-issued.
  - NOT AVAILABLE: whether haproxy then rejects the new backend with `kolla_verify_tls_backend: yes`
    (`group_vars/all.yml:1080`).
- **Oddity in key generation.** The backend key task writes `private/backend/backend.key` but its `creates:` checks
  `kolla_tls_backend_key` (`roles/certificates/tasks/generate-backend.yml:16-21`).
  - If an operator pre-supplies `backend-key.pem`, keygen is skipped but the CSR step still needs `backend.key`.
- **Distribution needs a separate run.** Certs only reach containers through `kolla-ansible reconfigure -i <inventory>
  -t haproxy` (PEM files) or a per-service reconfigure (backend and CA). Each of those means a container restart
  (sections 1.4 and 7).

---

## 9. Cross-cutting summary: restart triggers and blast radius

**Changed in 2025.1:** every restart below happens only when a compare of that container reports a change (image,
container parameters, unit text, `config.json` command, or a file its `config.json` lists); no config task notifies.

| Component | Restarted when | Hosts at once (default) | Blast radius |
|---|---|---|---|
| haproxy | `services.d`/haproxy.cfg/run.sh/PEM/CA/external-frontend-map/config.json change seen by a compare of the loadbalancer play (not under `-t <service>`, [F18](../findings.md#f18)), image change, any keepalived restart, unit-text drift ([F16](../findings.md#f16)) | all backups, then the VIP holder (all hosts at once if none holds the VIP) | all APIs plus database (ProxySQL) and other VIP traffic on the VIP holder while it restarts; VIP failover: NOT AVAILABLE |
| keepalived | keepalived.conf (inventory order!), config.json, checks, CA bundle, image change | all backups, then the VIP holder (stopped last) | VIP move or outage: NOT AVAILABLE |
| proxysql (on by default) | proxysql.yaml, users/rules files, PEM/CA, config.json, image change | all backups, then the VIP holder | database traffic through the VIP holder while it restarts: NOT AVAILABLE |
| haproxy_ssh | its files, config.json, CA bundle, image change (only with Let's Encrypt) | all loadbalancer hosts | certificate push by the lego container while it restarts: NOT AVAILABLE |
| memcached | config.json command (IP, port, memory, limit), image | all memcached hosts | whether all caches are emptied and Horizon users logged out: NOT AVAILABLE |
| chrony | no chrony role in 2025.1 | n/a | n/a |
| ovn-nb/sb-db | command line (IPs, bootstrap args), new `environment` (first 2025.1 run), image | all DB hosts | NB/SB API down; quorum re-election: NOT AVAILABLE |
| ovn-sb-db-relay (new) | relay config file or command, image | the changed relay numbers on all relay hosts | chassis and agents on that relay lose their SB connection: NOT AVAILABLE |
| ovn-northd | NB/SB host list, new `environment`, image | all northd hosts | logical-flow processing pause: NOT AVAILABLE |
| ovn-controller | image, drift, config.json command | **all computes and network nodes** | data-plane blip per chassis: NOT AVAILABLE |
| ovsdpdk-db → vswitchd | image, drift (db restart always notifies the vswitchd restart) | **all DPDK hosts** | VM data-plane outage: NOT AVAILABLE; followed by a fixed 300 s sleep (6.5) |

Things that run on **every** reconfigure, regardless of changes:
- loadbalancer config-host (sysctl role/modprobe) and the template set, plus 38 service includes and the second
  compare (`-t haproxy` or no tags).
- OVN setup-ovs (10 `kolla_toolbox` module calls per chassis), the OVN DB cluster lookup, the leader
  `set-connection` and the relay port waits.
- ovs-dpdk `install` + `bind_nics` (per DPDK host, **also on genconfig**).
- `compare_container` with an `<engine> exec kolla_set_configs --check` for every container on every host.

Things whose cost scales with the number of computes: ovn-controller config + setup-ovs, the number of OVN relays,
ovs-dpdk. The load balancer, memcached, the OVN DB and certificates scale only with control or loadbalancer hosts.
Chrony does not run on computes.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
