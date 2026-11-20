---
title: Fact sheet A
description: Fact sheet for the haproxy, haproxy-config, memcached, chrony, ovn, ovs-dpdk and service-cert-copy roles and the certificates playbook.
tags: [haproxy, keepalived, memcached, chrony, ovn, handlers, tags, serial]
---

# Fact sheet A

Scope: roles `haproxy` (incl. keepalived and the per-service `loadbalancer.yml` fan-out), `haproxy-config`,
`memcached`, `chrony`, `ovn`, `ovs-dpdk`, `service-cert-copy`, and the `certificates.yml` playbook/role.

All paths are relative to the repo root (`$SRC`). Tag `ussuri-eol`, HEAD `8a94fe9`.
Supported Ansible: 2.8–2.9 (`tools/kolla-ansible:58-59`).

How the evidence was gathered:
- **Code reading.** Every claim cites `path:line`.
- **Ansible semantics.** Tag inheritance, handler order and serial batches cite the Ansible 2.9.27 source as ansible
  2.9.27 `lib/ansible/<path>:N`. Ansible's own parse of `site.yml` is in
  [list-tags-site.txt](../listings/list-tags-site.txt).
- **Labels.** A claim with a `path:line` citation is a FACT read from the sources. `NOT AVAILABLE` marks what the
  sources do not establish, for example timings and runtime outcomes.

Common mechanics that apply to every role below (all verified in code):
- **All containers use host networking.** `kolla_docker` always uses host networking: `build_host_config` sets
  `'network_mode': 'host'` (`ansible/library/kolla_docker.py:717-719`). "net=host" is therefore never a role flag.
- **A config-only change means a full stop+start.** `config_strategy: "COPY_ALWAYS"` (`ansible/group_vars/all.yml:43`)
  is passed as `KOLLA_CONFIG_STRATEGY` in `docker_common_options` (`ansible/group_vars/all.yml:157-167`). With
  COPY_ALWAYS and no parameter drift, `recreate_or_restart_container` calls `restart_container`
  (`ansible/library/kolla_docker.py:781-801`), which does `dc.stop(name, timeout=graceful_timeout)` then `dc.start`
  (`kolla_docker.py:892-904`). `docker_graceful_timeout: 60` (`ansible/group_vars/all.yml:154`) arrives only through
  `common_options`, which the module default `graceful_timeout: 10` overrides, so the effective timeout is 10 s
  (`kolla_docker.py:991,1037-1047`; stop-timeout erratum in the [Per-role fact sheets](index.md)). **There is no
  "reload" path anywhere in scope.** The haproxy image ships a reload helper, `kolla_ensure_haproxy_latest_config`
  (kolla `docker/haproxy/Dockerfile.j2:20-21`, `docker/haproxy/ensure_latest_config.sh:5-14`), but kolla-ansible ussuri
  never calls it (grep finds no caller). The helper would not reload haproxy here anyway: it signals
  `haproxy-systemd-wrapper` (`:11`), which `haproxy_run.sh` does not start
  (`ansible/roles/haproxy/templates/haproxy_run.sh.j2:9`).
- **`kolla_serial` is only set for two actions.** The CLI passes it only for `upgrade` and `reconfigure`
  (`tools/kolla-ansible:430,439`), from `ANSIBLE_SERIAL`, which defaults to `0` = all hosts at once
  (`tools/kolla-ansible:236`).
- **Handlers fire in definition order across all hosts of the batch in lockstep** (linear strategy).
  - With the default serial 0, a handler restarts that container on **every host of the play at the same time**.
  - Ansible walks the play's handler list in order. It queues each notified handler on every notified host, then waits
    for all results before the next handler (ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:979-987`,
    `:1019-1035`). A notify sent by a handler is recorded while its results are processed (`:617-632`, `:784`;
    `lib/ansible/playbook/handler.py:47-51`), so a handler defined later and notified that way runs in the same flush.
- **Handlers are not tag-filtered in Ansible 2.9.**
  - Tags filter only the play's compiled task blocks and dynamically included blocks (ansible 2.9.27
    `lib/ansible/executor/play_iterator.py:186-189`, `lib/ansible/plugins/strategy/linear.py:371`). `run_handlers`
    has no tag check (`lib/ansible/plugins/strategy/__init__.py:972-987`). So under `-t <service>` the handler
    `Restart haproxy container` still runs, although it only carries the inherited play tag `haproxy`.

---

## 0. Plays in `ansible/site.yml` (summary table)

| Role | Play (lines) | Host pattern | Tags | serial |
|---|---|---|---|---|
| chrony | `site.yml:114-124` | `chrony-server`, `chrony`, `&enable_chrony_True` (116-119) | role-level `chrony` (123) | `kolla_serial` (120) |
| haproxy (+keepalived) | `site.yml:126-392` | `haproxy`, `&enable_haproxy_True` (128-130) | **play-level** `haproxy` (132-133) | `kolla_serial` (131) |
| haproxy-config | no play of its own. 49× `include_role <svc> tasks_from: loadbalancer` in a `block`, inside the haproxy play (`site.yml:138-392`) | haproxy hosts | per include: `<svc>`; nova/nova-cell: `[nova, nova-api]` / `[nova, nova-cell]` (296-305). Plus the inherited play tag `haproxy` | inherited |
| memcached | `site.yml:481-490` | `memcached`, `&enable_memcached_True` | role-level `[memcache, memcached]` (489) | `kolla_serial` (486) |
| ovs-dpdk | `site.yml:723-732` | `openvswitch`, `&enable_openvswitch_True_enable_ovs_dpdk_True` | role-level `ovs-dpdk` (731) | `kolla_serial` (728) |
| ovn | `site.yml:734-746` | `ovn-controller`, `ovn-nb-db`, `ovn-northd`, `ovn-sb-db`, `&enable_ovn_True` | role-level `ovn` (745) | `kolla_serial` (742) |
| service-cert-copy | no play. Imported from `<role>/tasks/copy-certs.yml` (52 roles, including haproxy) | caller's | caller's | caller's |
| certificates | separate playbook `ansible/certificates.yml:1-8` (`kolla-ansible certificates`, `tools/kolla-ansible:454-457`) | `localhost` | none | none |

- **Pattern groups.** The `enable_*` pattern groups are created by `group_by` in `site.yml:21-95`:
  - chrony line 30, haproxy 43, memcached 59, openvswitch/ovs_dpdk 68, ovn 70.
- **Play order matters.** It runs chrony (114) → haproxy (126) → … mariadb (473) → memcached (481) → … `nova.yml` (710)
  →
  openvswitch (712) → ovs-dpdk (723) → ovn (734) → … neutron (~761).
- **Common dependency.** haproxy, chrony, ovn and ovs-dpdk carry the meta dependency `- { role: common }`
  (`ansible/roles/{haproxy,chrony,ovn,ovs-dpdk}/meta/main.yml`). **memcached has no `meta/` at all**, so it has no
  common dependency.
  - The common role is guarded by `when: not common_run` and sets `common_run: True`
    (`ansible/roles/common/tasks/main.yml:2-10`).
  - It has `common_run: False` as a default (`ansible/roles/common/defaults/main.yml:4`).

---

## 1. `haproxy` role (haproxy + keepalived)

### 1.1 Play

- **Play:** `site.yml:126-392`. Hosts `haproxy` ∩ `enable_haproxy_True`, `serial: kolla_serial`, play-level
  `tags: [haproxy]`.
- **Role entry:** `- { role: haproxy, when: enable_haproxy | bool }` (135-136).
- **The loadbalancer block.** The play then has a `tasks:` block of 49 `include_role` statements (139-389) guarded by
  (390-392):
  ```yaml
  when:
    - enable_haproxy | bool
    - kolla_action in ['deploy', 'reconfigure', 'upgrade', 'config']
  ```
- **Role entry point.** `ansible/roles/haproxy/tasks/main.yml:2-3` is
  `include_tasks: "{{ kolla_action }}.yml"` with `when: inventory_hostname in groups['haproxy']`.
- **Default inventory.** `[haproxy:children] network` (`ansible/inventory/multinode:91-92`).

### 1.2 `haproxy_services` (`ansible/roles/haproxy/defaults/main.yml:2-18`)

| key | container | group | enabled | privileged | notable volumes |
|---|---|---|---|---|---|
| haproxy | `haproxy` | haproxy | `true` | **True** | `/etc/kolla/haproxy/:/var/lib/kolla/config_files/:ro`, named volume `haproxy_socket:/var/lib/kolla/haproxy/` (50-54) |
| keepalived | `keepalived` | haproxy | `enable_keepalived` | **True** | `/lib/modules:/lib/modules:ro`, `haproxy_socket:/var/lib/kolla/haproxy/` (55-60) |

- **Keepalived default.** `enable_keepalived: "{{ enable_haproxy | bool }}"` (`ansible/group_vars/all.yml:575`) and
  `enable_haproxy: "yes"` (574).
- **Shared socket volume.** The `haproxy_socket` volume is shared between both containers. The haproxy stats socket is
  `stats socket /var/lib/kolla/haproxy/haproxy.sock` (`templates/haproxy_main.cfg.j2:15`).
  - Confirmed in the kolla source: keepalived's `/check_alive.sh` lives in the kolla *image*, not in this repo, and
    runs `echo "show info" | socat unix-connect:/var/lib/kolla/haproxy/haproxy.sock stdio` (kolla
    `docker/keepalived/check_alive.sh:6`, baked in by kolla `docker/keepalived/Dockerfile.j2:22,25`).
- No pid_mode or ipc_mode is set.

### 1.3 Task flow per `kolla_action`

| action | task files (in order) | notes |
|---|---|---|
| deploy | `deploy.yml` → `config-host.yml` → `config.yml` → `check-containers.yml` (`deploy.yml:2-6`) | **No `flush_handlers`.** Comment `deploy.yml:8-11`: "haproxy role handlers should not be flushed early. site.yml handles all haproxy things in a dedicated play… See bug 1875228". The per-service loadbalancer includes then run (site.yml block) and the handlers flush once at the end of the play. |
| reconfigure | `reconfigure.yml:2` → `import_tasks: deploy.yml` | identical to deploy |
| upgrade | `config-host.yml` → `config.yml` → **"Stopping all slave keepalived containers"** → `check-containers.yml` (`upgrade.yml:2-19`) | see 1.8 |
| deploy-containers | `check-containers.yml` (`deploy-containers.yml:2`) | the loadbalancer block is **not** run (`site.yml:392`) |
| pull | `service-images-pull` (`pull.yml:2-3`): pulls images from `haproxy_services` (via `lookup('vars', project_name + '_services')`, `ansible/roles/service-images-pull/tasks/main.yml:14`) | |
| stop | `service-stop` with `haproxy_services` (`stop.yml:2-6`) | stops **both haproxy and keepalived on all haproxy hosts**, so no API frontend runs; whether the VIP is then released is NOT AVAILABLE. `skip_stop_containers` can exclude them (`ansible/roles/service-stop/tasks/main.yml:10-11`). |
| precheck | `precheck.yml` (939 lines, 79 tasks) | `service-precheck` group validation (2-6). Container facts (8-14). Whole-batch detection for the VIP checks (32-40, which skip when `--limit`/serial does not cover all haproxy hosts). Cert existence on localhost (42-74). External VIP iface present/active (76-86). VIPs not pingable (88-101, only when keepalived runs nowhere). Free ports (103-138). VIP in the same subnet as `api_interface` (141-153). `show stat` through the socket (155-164). Then one "free port" check per service on the VIP (166-939), skipped when that frontend already exists in `haproxy_stat`. |
| check | `check.yml` is empty | |
| config (genconfig) | `config.yml` only (no `config-host.yml`). The loadbalancer block **does** run (`'config'` is in the list, `site.yml:392`). | All handlers have `when: kolla_action != "config"` (`handlers/main.yml:16,36`), so nothing restarts. The next `deploy-containers` will detect drift through `kolla_set_configs --check` and restart. |

**Key tasks:**
- **`config-host.yml:2-26`.** These run on deploy, reconfigure and upgrade:
  - sysctl writes to `kolla_sysctl_conf_path` (`/etc/sysctl.conf`, `group_vars/all.yml:557`), only when
    `set_sysctl` (554): `net.ipv4.ip_nonlocal_bind=1`, `net.ipv6.ip_nonlocal_bind=1`,
    `net.ipv4.tcp_retries2=<haproxy_host_ipv4_tcp_retries2>`, `net.unix.max_dgram_qlen=128`.
  - The value `KOLLA_UNSET` (the default, `defaults/main.yml:76-78`) means `state: absent` (`config-host.yml:4-9`).
  - Then `module-load` with `ip_vs` (21-26). This is loaded even when `enable_keepalived` is false, because it has no
    `when`.
- **`check-containers.yml:2-17`.** `compare_container` for each enabled service, notifying
  `"Restart {{ item.key }} container"`.

### 1.4 Config files generated (`ansible/roles/haproxy/tasks/config.yml`)

| dest (host) | source / override order | notifies |
|---|---|---|
| `/etc/kolla/{haproxy,keepalived}/` dirs (2-13), `/etc/kolla/haproxy/services.d/` (15-27) | n/a | none |
| `/etc/kolla/<svc>/config.json` (29-40) | `templates/haproxy.json.j2`, `templates/keepalived.json.j2` | `Restart haproxy container` / `Restart keepalived container` |
| `/etc/kolla/haproxy/haproxy.cfg` (42-58) | first_found: `{{node_custom_config}}/haproxy/<inventory_hostname>/haproxy_main.cfg` → `{{node_custom_config}}/haproxy/haproxy_main.cfg` → `haproxy_main.cfg.j2` | Restart haproxy container |
| `/etc/kolla/haproxy/services.d/*.cfg` (60-74) | `with_fileglob: {{node_custom_config}}/haproxy/services.d/*.cfg` (operator custom frontends) | Restart haproxy container |
| `/etc/kolla/keepalived/keepalived.conf` (76-92) | first_found: `…/keepalived/<host>/keepalived.conf` → `…/keepalived/keepalived.conf` → `keepalived.conf.j2` | Restart keepalived container |
| `/etc/kolla/haproxy/haproxy.pem` (94-109) | `copy` from `kolla_external_fqdn_cert` (`/etc/kolla/certificates/haproxy.pem`, `group_vars/all.yml:800`), when `kolla_enable_tls_external` | Restart haproxy container |
| `/etc/kolla/haproxy/haproxy-internal.pem` (111-126) | from `kolla_internal_fqdn_cert` (801), when `kolla_enable_tls_internal` | Restart haproxy container |
| `/etc/kolla/{haproxy,keepalived}/ca-certificates/` (128-130 → `copy-certs.yml` → `service-cert-copy`) | `{{kolla_certificates_dir}}/ca/`, only when `kolla_copy_ca_into_containers` | **both** `Restart haproxy container` **and** `Restart keepalived container` (see section 7) |
| `/etc/kolla/haproxy/haproxy_run.sh` (132-148) | first_found: `…/haproxy/<host>/haproxy_run.sh` → `…/haproxy/haproxy_run.sh` → `haproxy_run.sh.j2` | Restart haproxy container |
| `/etc/kolla/haproxy/services.d/<service-key>.cfg` | written by **haproxy-config** (section 2) from each service role's `loadbalancer.yml` | Restart haproxy container |

Inside the container:
- **haproxy.json.j2.** It copies `haproxy_run.sh`, `haproxy.cfg`, the whole `services.d/` directory and the two pem
  files (marked optional when TLS is off) (`templates/haproxy.json.j2:2-36`).
- **haproxy_run.sh.j2:7-9.** It runs `haproxy -W -db -p /run/haproxy.pid -f /etc/haproxy/haproxy.cfg` plus one `-f`
  per file found by `find /etc/haproxy/services.d/ -mindepth 1`. That is *every* file, not only `*.cfg`.
  - It is started in master-worker mode (`-W`), which could do a SIGUSR2 reload, but Kolla never uses that.
- **haproxy_main.cfg.j2.**
  - `listen stats` is on `api_interface_address:haproxy_stats_port` (1984) (38-45).
  - `frontend status` (monitor-uri) is on `api_interface_address:61313` and on `VIP:61313` (47-53).
  - `haproxy_monitor_port: "61313"` (`group_vars/all.yml:320`).
- **keepalived.conf.j2:**
  - `vrrp_script check_alive { script "/check_alive.sh" interval 2 fall 2 rise 10 }` (1-6).
  - `state BACKUP` + `nopreempt` (9-10).
  - **`priority {{ groups['haproxy'].index(inventory_hostname) + 1 }}`** (13).
  - Unicast peers are built from `groups['haproxy']` (15-27). The VIP(s) are at 28-33. `track_interface` for the
    external VIP (34-38). `auth_type PASS` (39-42). `track_script check_alive` (43-45).
  - `keepalived_virtual_router_id: "51"` (`group_vars/all.yml:186`). `keepalived_traffic_mode: "multicast"`
    (`defaults/main.yml:38`).

### 1.5 Handlers (`ansible/roles/haproxy/handlers/main.yml`). Definition order = run order (see common mechanics)

1. **`Restart haproxy container`** (2-20).
   - `kolla_docker: recreate_or_restart_container`.
   - `when: kolla_action != "config"`, host in `groups['haproxy']`, enabled.
   - `notify: Waiting for haproxy to start`.
2. **`Restart keepalived container`** (22-40). Same as above; `notify: Waiting for virtual IP to appear`.
3. **`Waiting for haproxy to start`** (42-45).
   - `wait_for host: api_interface_address port: haproxy_monitor_port` (default 300 s timeout).
   - It only proves that the haproxy process listens. It says nothing about the backends.
4. **`Waiting for virtual IP to appear`** (47-50).
   `wait_for host: kolla_internal_vip_address port: haproxy_monitor_port`.

Other properties:
- There is no `run_once`, `delegate_to`, `listen`, rolling or serial logic inside the handlers.
- Restarts are parallel across all haproxy hosts unless `ANSIBLE_SERIAL`/`kolla_serial` is set.
  - With `kolla_serial=1`, Ansible runs the whole play, handler flushes included, once per one-host batch: one
    restart plus wait per host, batch by batch (ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:161-169`,
    `:276-285`; flush points `lib/ansible/playbook/play.py:276-281`).
- No other role notifies these handlers. The only external notifier is `ansible/roles/haproxy-config/tasks/main.yml:21`
  (grep over `ansible/roles`).

### 1.6 Bootstrap / DB / Keystone / RabbitMQ registration

None.

### 1.7 Dependencies

- **VIP-related variables.** `kolla_internal_vip_address`, `kolla_external_vip_address` (`group_vars/all.yml:50-52`),
  `haproxy_enable_external_vip` (796), `api_interface`, `kolla_external_vip_interface` (223-224).
- **TLS:** `kolla_enable_tls_{internal,external}` and the cert paths (797-801). These are produced by the
  `certificates` playbook (section 8) or supplied by the operator.
- **Everything behind the VIP.** Every service's `loadbalancer.yml` (section 2) builds backend lists from
  `groups[<svc group>]` and `hostvars[host].ansible_facts.hostname`, so facts are needed for all backend hosts (handled
  by `ansible/gather-facts.yml`, including the `--limit` path at 29-50).
  - `database_address: "{{ kolla_internal_fqdn }}"` (`group_vars/all.yml:105`) and `kolla_internal_fqdn` = the VIP
    (51). So **all DB traffic goes through haproxy**.
- **chrony.** `chrony-server` = `haproxy` hosts (`inventory/multinode:47-48`), and chrony serves on the VIP (section 4).
- **Logging.** `syslog_server: "{{ api_interface_address }}"` and `syslog_udp_port` (fluentd) (`defaults/main.yml:34`,
  `group_vars/all.yml:504`). This needs fluentd from `common`.

### 1.8 Operationally notable behaviour

- **(A) Any change means a full restart of haproxy on all haproxy nodes at once, never a reload.**
  - Every haproxy-relevant change goes to `Restart haproxy container`, which is `restart_container` (docker stop with
    SIGKILL after 10 s at the latest, see the stop-timeout erratum in the [Per-role fact sheets](index.md), then docker
    start). That includes a change in any one service's `services.d/<svc>.cfg`, a cert, haproxy.cfg or haproxy_run.sh.
  - With the default `serial 0`, all haproxy hosts restart in the same handler step. Result: every API, MariaDB
    (through the VIP, `group_vars/all.yml:105`), RabbitMQ management, etc. is served by a haproxy that is restarting.
  - NOT AVAILABLE: how long the outage lasts per run, and whether established connections are cut. From the code:
    `haproxy_run.sh` does not `exec` haproxy (`haproxy_run.sh.j2:7-9`), so dumb-init's child is bash, not haproxy
    ([Kolla images §2.6](../../concepts/kolla-images.md#26-signals-and-pid-1)). Whether haproxy itself gets the SIGTERM
    of `docker stop` is NOT AVAILABLE; a container still running after 10 s is stopped with SIGKILL.
- **(B) Whether a haproxy restart causes VIP failover or a VIP outage is NOT AVAILABLE.**
  - keepalived tracks `check_alive` with `interval 2 fall 2 rise 10` (`keepalived.conf.j2:1-6`).
  - NOT AVAILABLE: whether keepalived goes to FAULT and drops the VIP while haproxy is down on the VIP holder, and how
    long the VIP is then absent. The backups restart haproxy in the same handler step (serial 0). The "Waiting for
    haproxy" handler checks `api_interface_address`, not the VIP (`handlers/main.yml:42-45`).
  - `nopreempt` is set (line 10). Which node holds the VIP afterwards is NOT AVAILABLE.
  - The check itself is known: the image's `/check_alive.sh` only asks the haproxy stats socket for `show info`
    (kolla `docker/keepalived/check_alive.sh:6`), so it fails as soon as haproxy stops answering on the socket. The
    FAULT and `rise` timing is upstream keepalived behaviour. NOT AVAILABLE: the timing and keepalived's initial script
    state.
- **(C) keepalived priority depends on inventory order.**
  - `priority = index in groups['haproxy'] + 1` (`keepalived.conf.j2:13`).
  - Inserting, removing or re-ordering a haproxy host changes `keepalived.conf` on every host after it in the list. In
    unicast mode it changes on all hosts (peer list, 18-25). Each changed host restarts keepalived (in parallel).
    Whether that moves or flaps the VIP is NOT AVAILABLE.
- **(D) Stale frontends are never removed.**
  - Nothing in the tree deletes files in `services.d` (grep: no `state: absent` in `roles/haproxy*`).
  - If a service is disabled (`enable_X: no`), its `include_role` is skipped (`when: enable_X`). The old
    `/etc/kolla/haproxy/services.d/X.cfg` stays and is loaded by `haproxy_run.sh` on the next restart.
  - The same is true for removed custom `node_custom_config/haproxy/services.d/*.cfg` files.
  - BUG/oddity (code fact).
- **(E) `-t haproxy` also runs `common` on haproxy hosts.**
  - common is a meta dependency, and its tasks inherit the play tag `haproxy` (ansible 2.9.27
    `lib/ansible/playbook/block.py:351-358`). Ansible's own parse lists `common` among the haproxy play's task tags
    ([list-tags-site.txt](../listings/list-tags-site.txt), play #7).
  - So `kolla-ansible -t haproxy reconfigure` also reconfigures fluentd, cron and kolla-toolbox on the haproxy hosts
    (guarded only by `common_run`).
- **(F) Upgrade "Stopping all slave keepalived containers"** (`upgrade.yml:6-17`):
  ```yaml
  vars:
    key: "{{ 'ipv6' if api_address_family == 'ipv6' else 'ipv4_secondaries' }}"
    addresses: "{{ hostvars[inventory_hostname].ansible_facts[api_interface].get(key, []) | map(attribute='address') | list }}"
  kolla_docker: { action: "stop_container", name: "keepalived" }
  when: kolla_internal_vip_address not in addresses
  notify: [ Restart keepalived container ]
  ```
  - On upgrade, keepalived is stopped on every non-VIP host and recreated in the handler phase. This is the fix for
    LP#1928362 (`releasenotes/notes/fix-keepalived-upgrade-a395e39dc946e618.yaml`).
  - The handler order is: Restart haproxy on all hosts, then Restart keepalived on all hosts (including the VIP holder
    if its image changed), then the waits.
  - **Likely BUG 1.** The task has no `when: enable_keepalived`, and `stop_container` fails when the container is
    missing (`ignore_missing` defaults to False, `kolla_docker.py:871-881,1012`).
    - With `enable_keepalived: no` (external LB, `releasenotes/notes/allow-disabling-keepalived-…yaml`) the VIP is on
      no haproxy host. The task therefore runs everywhere and should fail with "No such container: keepalived to stop".
    - The same applies to a haproxy host added without a keepalived container. The end-to-end upgrade outcome is
      NOT AVAILABLE.
  - **Likely BUG 2.** It indexes `ansible_facts[api_interface]` with the raw interface name. Ansible converts `-` to `_`
    in fact names (ansible 2.9.27 `lib/ansible/module_utils/facts/namespace.py:41`), whereas Kolla's own
    `kolla_address` filter does the conversion (`kolla_ansible/kolla_address.py:88`).
    - So an `api_interface` like `br-mgmt` is not a key of `ansible_facts` under that name.
    - The same pattern appears in `precheck.yml:86` (`ansible_facts[kolla_external_vip_interface]['active']`).
    - NOT AVAILABLE: whether `upgrade` (or that precheck) then fails at run time.
- **(G) Things that run on every deploy, reconfigure and upgrade:**
  - sysctl + modprobe (config-host).
  - About 12 template/copy tasks.
  - 2× `compare_container`, each of which does a `docker exec kolla_set_configs --check`.
  - Plus up to 49 service includes, each compiling its role and the role's `common` dependency, which is then deduped
    and skipped.
  - The cost scales with the number of haproxy hosts, not with computes.
  - The `sysctl` task with `KOLLA_UNSET` *removes* any manual `net.ipv4.tcp_retries2` line from `/etc/sysctl.conf` on
    every run (`config-host.yml:4-10`).
- **(H) Non-local bind is needed.**
  - `ip_nonlocal_bind=1` is set only when `set_sysctl` is true (`config-host.yml:17-19`). Backup nodes bind VIP
    addresses (`haproxy_main.cfg.j2:50`, every frontend).
  - NOT AVAILABLE: whether haproxy starts on non-VIP nodes with `set_sysctl: no` and no manual sysctl.
- **(I) VRRP router id collisions.** `keepalived_virtual_router_id` defaults to `51` with multicast. Two Kolla clouds on
  the same L2 segment collide unless it is changed (`group_vars/all.yml:186`, `defaults/main.yml:38`).

### 1.9 What exactly happens in the haproxy play for `-t <service>` and `-t haproxy`

How the tags combine (the mechanics):
1. **Play tag.** It is inherited by everything statically in the play: the role tasks, the `block`, and each
   `include_role` statement. A role task ends up with tags `{haproxy}`, and common's two `main.yml` tasks with
   `{common, haproxy}` (`ansible/roles/common/tasks/main.yml:2-3,9`). `tags` is an extending attribute that collects
   the role, dependency chain and play values (ansible 2.9.27 `lib/ansible/playbook/taggable.py:31`,
   `lib/ansible/playbook/block.py:329-358`).
2. **Include tags.** The `include_role` statement for keystone has tags `{keystone, haproxy}`.
3. **Dynamic include boundary.** `include_role` is *dynamic*. Ansible 2.9 does not pass the include's own tags to the
   included tasks: when the parent is not `statically_loaded`, `Task._get_parent_attribute` skips to the grandparent
   (ansible 2.9.27 `lib/ansible/playbook/task.py:466-472`; the same for blocks, `lib/ansible/playbook/block.py:309-314`;
   an include is not statically loaded, `lib/ansible/playbook/task_include.py:56`). So the tasks inside
   `keystone/tasks/loadbalancer.yml` would only carry `{haproxy}`, and would be filtered out under `-t keystone`.
4. **The `tags: always` workaround.** Kolla works around this with `tags: always` on the
   `import_role: haproxy-config` in every `loadbalancer.yml`, e.g. `ansible/roles/keystone/tasks/loadbalancer.yml:2-7`:
   ```yaml
   - name: "Configure haproxy for {{ project_name }}"
     import_role:
       name: haproxy-config
     vars:
       project_services: "{{ keystone_services }}"
     tags: always
   ```
   The same applies to `nova-cell` (`ansible/roles/nova-cell/tasks/loadbalancer.yml:55,91,127`,
   `proxy_loadbalancer.yml:19`, `cell_proxy_loadbalancer.yml:12`).
5. **Handlers ignore tags.** They run whenever they are notified (see common mechanics).

**`kolla-ansible -t keystone reconfigure`.** From the rules above and the tag test in ansible 2.9.27
`lib/ansible/playbook/taggable.py:66-76` (`always` always matches):
- haproxy role tasks are **skipped**. They are tagged only `haproxy`. That covers config-host, config.yml (haproxy.cfg,
  keepalived.conf, pems, haproxy_run.sh, custom services.d), check-containers, and the `common` dependency.
- Exactly **one** `include_role` runs: keystone's (`site.yml:229-233`). It is skipped if `enable_keystone` is false.
  The other 48 `include_role` statements are skipped by tag.
- haproxy-config renders `/etc/kolla/haproxy/services.d/keystone.cfg` only, on every haproxy host. Only service keys
  that have a `haproxy:` dict and are enabled are rendered.
- If and only if that file changed, `Restart haproxy container` runs at the end of the haproxy play. It runs on all
  haproxy hosts in parallel (serial 0), then `Waiting for haproxy to start`.
  - **keepalived is not restarted**, because nothing notifies it. Whether the VIP still moves because of (B) is
    NOT AVAILABLE.
- The restart re-reads **all** `services.d/*` files.
  - Any drift left in `/etc/kolla/haproxy/` by earlier runs (e.g. a previous `genconfig`, or stale files) goes live too.
  - Other services' `.cfg` files are **not re-rendered**. If another service's backend list changed (say, a new
    controller), it is not updated by `-t keystone`.
- Cert rotation for the VIP needs `-t haproxy`. The pem copy is a haproxy role task.
- `--skip-tags haproxy` skips the whole play, including all per-service includes: each one carries the inherited
  play tag, and a task with a skipped tag does not run (ansible 2.9.27 `lib/ansible/playbook/taggable.py:78-87`).
- Tag aliases:
  - `-t nova` hits both nova and nova-cell (296-306).
  - `-t memcache` (alias tag of the memcached play, `site.yml:489`) does **not** hit memcached's include, which is
    tagged only `memcached` (262).

**`kolla-ansible -t haproxy reconfigure`.**
- `common` runs on the haproxy hosts (when `common_run` is false). Then the haproxy role runs `reconfigure.yml` →
  `deploy.yml`: config-host, config.yml (all files in 1.4), check-containers.
- **All 49** `include_role` statements match, through the inherited play tag. Every enabled service's `services.d/*.cfg`
  is re-rendered.
  - `placement`'s include has **no `when`** (`site.yml:289-292`). `placement-api.cfg` is always written, and is empty
    if `enable_placement` is false (`ansible/roles/placement/defaults/main.yml:7,12,19`).
- End-of-play handlers, in this order:
  - Restart haproxy, if anything changed.
  - Restart keepalived, if `keepalived.conf`, keepalived `config.json`, CA certs or container params changed.
  - Wait for haproxy.
  - Wait for the VIP.
- No service containers (keystone etc.) are touched.

**`kolla-ansible reconfigure` (no tags).** Same as `-t haproxy`, plus all the other plays. It is still a single haproxy
restart per run, at the end of the haproxy play (the fix for LP#1864810/LP#1875228,
`releasenotes/notes/bug-1864810-5a5d0f91c0171b19.yaml`). The restart happens only if any rendered file changed.

**`deploy-containers` and `-t <svc> deploy-containers`.** Only haproxy `check-containers.yml` runs, and only under
`-t haproxy` or no tags. The services.d includes do not run (`site.yml:392`).

---

## 2. `haproxy-config` role

### 2.1 How it is applied

- Only through `import_role` (with `tags: always`) from the 49 `ansible/roles/*/tasks/loadbalancer.yml` files, which are
  `include_role`'d by the haproxy play (`site.yml:139-389`).
  - Every role that has a `loadbalancer.yml` is included; a diff of the two lists is empty.
  - `nova-cell` loops over cells (`ansible/roles/nova-cell/tasks/proxy_loadbalancer.yml:5-19` →
    `cell_proxy_loadbalancer.yml:3-12`, using `namespace_haproxy_for_cell`).
- No defaults-level `_services` dict of its own. It consumes `project_services`.

### 2.2 Task (`ansible/roles/haproxy-config/tasks/main.yml:2-21`), the only task

```yaml
- name: "Copying over {{ project_name }} haproxy config"
  vars:
    service: "{{ item.value }}"
    haproxy_templates:
      - "{{ node_custom_config }}/haproxy-config/{{ inventory_hostname }}/{{ haproxy_service_template }}"
      - "{{ node_custom_config }}/haproxy-config/{{ haproxy_service_template }}"
      - "templates/{{ haproxy_service_template }}"
    template_file: "{{ query('first_found', haproxy_templates) | first }}"
  template:
    src: "{{ template_file }}"
    dest: "{{ node_config_directory }}/haproxy/services.d/{{ item.key }}.cfg"
  when: [ service.enabled | bool, service.haproxy is defined, enable_haproxy | bool ]
  with_dict: "{{ project_services }}"
  notify: [ Restart haproxy container ]
```
- **Template choice.** `haproxy_service_template` defaults to `haproxy_single_service_listen.cfg.j2`
  (`defaults/main.yml:2`). The alternative is `haproxy_single_service_split.cfg.j2` (frontend/backend split). Operators
  can override per host or globally under `/etc/kolla/config/haproxy-config/`.
- **Extras and health checks.**
  - Global extras: `haproxy_frontend_http_extra: [option httplog, option forwardfor]` and
    `haproxy_frontend_tcp_extra: [option tcplog]` (`defaults/main.yml:5-11`).
  - Health check: `check inter 2000 rise 2 fall 5`, or with `check-ssl` (13-14).
- **Backend list.** From the listen template:
  `{% for host in groups[host_group] %} server {{ hostvars[host].ansible_facts.hostname }} {{ 'api'|kolla_address(host) }}:{{ listen_port }} …`
  (`templates/haproxy_single_service_listen.cfg.j2:73-77`).
  - `host_group` defaults to `service.group` (96). `custom_member_list` overrides it (57-60), as in memcached and
    mariadb.
- **Binding and TLS.**
  - External entries bind `kolla_external_vip_address`; internal entries bind `kolla_internal_vip_address` (37-52).
  - External entries are dropped when `haproxy_enable_external_vip` is false (87).
  - `tls_backend` adds `ssl verify required ca-file <haproxy_backend_cacert>` when `kolla_verify_tls_backend` (63-69).

### 2.3 Handler

It has none of its own. It notifies `Restart haproxy container`, defined in the haproxy role. The handler is resolvable
because the haproxy role is in the same play.

`include_role` also *appends the included role's handlers* to the play (ansible 2.9.27
`lib/ansible/playbook/role_include.py:110-114`).
They are never notified here, so this is harmless.

### 2.4 Notable

- **Stale files are not removed** (see 1.8 D).
- If a service's `enabled` is false, the task is skipped and the file is left as it was. It is not emptied.
- **File name.** The file is named after the `<svc>_services` *key* (e.g. `keystone.cfg`, `placement-api.cfg`), not the
  project name.
- **Facts are required.** It depends on facts for every backend host
  (`hostvars[host].ansible_facts.hostname`, listen template line 74).
- **Precedence.** Variables come from the service role's defaults, evaluated on the haproxy host. Inventory or
  group_vars overrides of service variables therefore apply when set for the haproxy hosts or for `all`.
  - NOT AVAILABLE: whether per-host overrides set only on backend hosts are seen by haproxy-config, outside the places
    where the code explicitly uses `hostvars[groups[…][0]]` (nova-cell).

---

## 3. `memcached` role

### 3.1 Play

`site.yml:481-490`: hosts `memcached` ∩ `enable_memcached_True`, `serial: kolla_serial`, role tags
`[memcache, memcached]`. No meta dependency on `common`. The default inventory is `[memcached:children] control`
(`inventory/multinode:158-159`).

### 3.2 `memcached_services` (`ansible/roles/memcached/defaults/main.yml:2-21`)

| key | container | group | enabled | flags |
|---|---|---|---|---|
| memcached | `memcached` | memcached | `true` | not privileged; volumes are only config, localtime and timezone (37-41) |

- **Haproxy entry.** It has a haproxy sub-entry `memcached` (tcp, port 11211) with
  `enabled: enable_memcached and enable_haproxy_memcached` (12).
  - `enable_haproxy_memcached: "no"` by default (`group_vars/all.yml:584-587`). The comment there: clients do
    client-side hashing.
  - Its backend list is `custom_member_list` built from `haproxy_members` (26): the first host is active, the others
    are `backup`.
- **Tunables.** `memcached_connection_limit: 5000` and `memcached_max_memory: 256` (MB) (46-49).
- **Container command:** `memcached -v -l <api_interface_address> -p 11211 -c 5000 -U 0 -m 256`
  (`templates/memcached.json.j2:2`), with no `config_files`.

### 3.3 Task flow

- `main.yml:2` is `include_tasks "{{ kolla_action }}.yml"` (no host guard).
- **deploy** = `config.yml` + `check-containers.yml` (`deploy.yml:2-4`). No flush; the handler runs at the end of the
  memcached play.
- **reconfigure** = deploy.
- **upgrade** = config + check-containers (`upgrade.yml:2-4`).
- **deploy-containers** = check-containers.
- **pull** = service-images-pull.
- **stop** = service-stop.
- **precheck** = `service-precheck` + free port on `api_interface_address:11211` when the container is absent
  (`precheck.yml:2-24`).
- **check** = empty.
- **config** = config.yml.
- Loadbalancer part: `tasks/loadbalancer.yml:2-7`, through the haproxy play (`site.yml:259-263`, tag `memcached`).

### 3.4 Config files

- **Only `/etc/kolla/memcached/config.json`** (`config.yml:13-26`), which notifies `Restart memcached container`.
- No custom-override path (there is no config file).
- The directory task has no group guard (`config.yml:2-11`).

### 3.5 Handlers

- `Restart memcached container` (`handlers/main.yml:2-14`): `recreate_or_restart_container`,
  `when: kolla_action != "config"`.
- It runs on all memcached hosts in parallel at the end of the play.

### 3.6 Bootstrap

None.

### 3.7 Dependencies (consumers of memcached)

- **Every service builds its memcache server list from `groups['memcached']`.**
  - 43 role files reference `groups['memcached']`; 48 templates set `memcache(d)_servers`.
  - Keystone example: `backend = oslo_cache.memcache_pool` and
    `memcache_servers = {% for host in groups['memcached'] %}…`
    (`ansible/roles/keystone/templates/keystone.conf.j2:49-51`).
  - Horizon uses memcached as the **session store** when `horizon_backend_database` is false
    (`SESSION_ENGINE = 'django.contrib.sessions.backends.cache'`,
    `ansible/roles/horizon/templates/local_settings.j2:177-185`).
    `horizon_backend_database` defaults to `enable_murano` (`group_vars/all.yml:982`).

### 3.8 Operationally notable

- **All memcached instances restart at once.** FACT: they restart simultaneously (serial 0); the container mounts no
  data volume (`defaults/main.yml:37-40`) and its command has no persistence option (`templates/memcached.json.j2:2`).
  - NOT AVAILABLE: whether a restart therefore empties every cache at the same time, whether Horizon users are logged
    out (cache session backend), and whether the cold Keystone and keystonemiddleware token-validation caches give a
    load spike on Keystone and the DB.
  - Triggers are rare: a change of `api_interface_address`, port, memory or connection limit, or an image change on
    upgrade.
- **Adding or removing a memcached host is expensive.** It changes the `memcache_servers` of almost every service
  config, which means a restart of most API containers on the next full reconfigure. That cost sits outside this role.
- **Tag aliases differ.** `-t memcache` reconfigures the container but not its haproxy file. Only `-t memcached` does
  both.
- **memcached has no `common` dependency.** Unlike most roles, memcached does not pull in `common`.

---

## 4. `chrony` role

### 4.1 Play

`site.yml:114-124`: hosts `chrony-server` ∪ `chrony` ∩ `enable_chrony_True`, `serial: kolla_serial`, role tag `chrony`,
`when: enable_chrony` (`enable_chrony: "yes"`, `group_vars/all.yml:597`).
- Default inventory: `chrony-server` = haproxy (`inventory/multinode:47-48`); `chrony` = control, network, compute,
  storage, monitoring (50-55). So it runs on **every host, including all computes**.
- It is the **first** service play, before haproxy.

### 4.2 `chrony_services` (`ansible/roles/chrony/defaults/main.yml:2-10`)

| key | container | group | enabled | flags |
|---|---|---|---|---|
| chrony | `chrony` | chrony | `True` | **privileged: True** (it sets the host clock); volumes: config, localtime, timezone, `kolla_logs` (24-28). There is no persistent `/var/lib/chrony` volume, so the drift file is lost on recreate. |

`chrony_bindaddress: "{{ kolla_internal_vip_address }}"` (12).

### 4.3 Task flow

- **deploy** = `config.yml` → `check-containers.yml` → **`meta: flush_handlers`** (`deploy.yml:2-7`).
- **reconfigure** = deploy. **upgrade** = deploy (`upgrade.yml:2`).
- **deploy-containers** = check-containers.
- **pull** and **stop** use the generic roles.
- **precheck** = service-precheck only (`precheck.yml:2-9`; a TODO notes that there is no UDP/123 check).
- **check** = empty. **config** = config.yml.

### 4.4 Config files (`ansible/roles/chrony/tasks/config.yml`)

| dest | source | notifies |
|---|---|---|
| `/etc/kolla/chrony/config.json` (19-34) | `chrony.json.j2` | Restart chrony container |
| `/etc/kolla/chrony/chrony.conf` (36-53) | first_found: `{{node_custom_config}}/chrony/<host>/chrony.conf` → `{{node_custom_config}}/chrony/chrony.conf` → `chrony.conf.j2` | Restart chrony container |

`chrony.conf.j2` content:
- `server <VIP> iburst` (3), plus `server` lines for each `external_ntp_servers` entry, on **all** hosts (5-9).
  - The default list is `0-3.pool.ntp.org` (`group_vars/all.yml:96-100`).
- On `chrony-server` hosts: `allow all`, `deny VIP`, `deny api_interface_address`, `local stratum 10` (30-35).
  Otherwise: `port 0`, `deny all` (36-38).
- `bindaddress {{ chrony_bindaddress }}` (41).
- `makestep 3 3` (22).

### 4.5 Handlers

`Restart chrony container` (`handlers/main.yml:2-16`): `recreate_or_restart_container`,
`when: kolla_action != "config"`.
It is flushed inside the chrony play.

### 4.6 Bootstrap

None.

### 4.7 Dependencies

- The VIP (keepalived, which is configured *later* in the same run) and the haproxy group (as `chrony-server`).
- `ip_nonlocal_bind`, which is set later by `haproxy/config-host.yml`.
  - NOT AVAILABLE: whether, on a first deploy, chronyd on a non-VIP chrony-server host can bind the VIP before
    `ip_nonlocal_bind` is set, and whether it then serves before a later restart.
- External NTP reachability.
- On Ubuntu, `baremetal` removes the host chronyd AppArmor profile
  (`ansible/roles/baremetal/tasks/post-install.yml:195-209`).

### 4.8 Operationally notable

- **Low data-plane risk.**
  - NOT AVAILABLE: whether a restart steps the clock. `makestep 3 3` is set (`chrony.conf.j2:22`).
- **Cost scales with the number of hosts.** One template, one config.json and one `compare_container` with a
  `docker exec` run on **every compute** on each run.
- **chrony.conf depends on the haproxy group.** It changes on a host when that host's membership in `chrony-server`
  changes, or when the VIP or `external_ntp_servers` change.
- **The VIP is the internal time source.** When the VIP fails over to another haproxy node, clients keep the same server
  IP but get a different clock source.
  - NOT AVAILABLE: whether reachable external NTP servers mitigate this.

---

## 5. `ovn` role

### 5.1 Play

`site.yml:734-746`: hosts `ovn-controller` ∪ `ovn-nb-db` ∪ `ovn-northd` ∪ `ovn-sb-db`, ∩ `enable_ovn_True`;
`serial: kolla_serial`; role tag `ovn`.
- `enable_ovn: "{{ enable_neutron | bool and neutron_plugin_agent == 'ovn' }}"` (`group_vars/all.yml:685`).
- Default inventory (`inventory/multinode:788-808`):
  - `ovn-controller` = `ovn-controller-compute` (= compute) + `ovn-controller-network` (= network).
  - `ovn-database` = control.
  - `ovn-northd`, `ovn-nb-db` and `ovn-sb-db` are each `ovn-database`.
- So the play covers **all computes**. It runs after the openvswitch/ovs-dpdk plays and before neutron.

### 5.2 `ovn_services` (`ansible/roles/ovn/defaults/main.yml:2-30`)

| key | container | group | enabled | flags / volumes |
|---|---|---|---|---|
| ovn-controller | `ovn_controller` | ovn-controller | true | **`/run/openvswitch:/run/openvswitch:shared`**, kolla_logs (60-64); not privileged |
| ovn-northd | `ovn_northd` | ovn-northd | true | config, localtime, logs (65-68) |
| ovn-nb-db | `ovn_nb_db` | ovn-nb-db | true | named volume **`ovn_nb_db:/var/lib/openvswitch/ovn-nb/`** (69-73) |
| ovn-sb-db | `ovn_sb_db` | ovn-sb-db | true | named volume **`ovn_sb_db:/var/lib/openvswitch/ovn-sb/`** (74-78) |

`ovn_remote_probe_interval: "60000"` (90).

### 5.3 Task flow

- `main.yml:2`: `include_tasks "{{ kolla_action }}.yml"`.
- **deploy** = `config.yml` → `check-containers.yml` → **`bootstrap.yml`** → `meta: flush_handlers` (`deploy.yml:2-9`).
- **reconfigure** = deploy. **upgrade** = the same four steps (`upgrade.yml:2-9`).
- **deploy-containers** = check-containers only (no bootstrap, no explicit flush).
- **pull**/**stop** use the generic roles (`stop.yml` uses `ovn_services`).
- **precheck** = free-port checks for 6641/6642 only (`precheck.yml:2-30`). There is **no `service-precheck`
  group validation**.
- **check** = empty. **config** = config.yml.

**bootstrap.yml runs on every deploy, reconfigure and upgrade.** Each task is a
`command: docker exec openvswitch_vswitchd ovs-vsctl …`
with no `changed_when`, so each reports *changed* on every run:

| task (lines) | hosts | effect |
|---|---|---|
| Create br-int (2-7) | ovn-controller | `--may-exist add-br br-int -- set Bridge br-int fail-mode=secure` |
| OVN encapsulation (9-16) | ovn-controller | `external_ids:ovn-encap-ip=<tunnel_interface_address> ovn-encap-type=geneve ovn-remote=<ovn_sb_connection>` |
| Bridge mappings (18-25) | ovn-controller-network, or computes if `computes_need_external_bridge` (`group_vars/all.yml:949`) | `ovn-bridge-mappings=physnet1:<br>,…` from `neutron_bridge_name` |
| Enable chassis as gateway (27-30) | ovn-controller-network | `external-ids:ovn-cms-options="enable-chassis-as-gw"`. This **overwrites** the whole `ovn-cms-options` value. |
| Disable gateway (32-37) | hosts in `openvswitch` but not in `ovn-controller-network` | `ovs-vsctl remove … external-ids ovn-cms-options` |
| Remote probe interval (39-45) | ovn-controller | `ovn-remote-probe-interval=60000` |

### 5.4 Config files

Only `config.json` per service (`config.yml:15-26`), which notifies `Restart <key> container`. There are no other files
and no custom-override paths. The entire configuration is on the command line:
- **ovn-nb-db and ovn-sb-db** (`templates/ovn-nb-db.json.j2:2`, `ovn-sb-db.json.j2:2`):
  - `ovn-ctl run_nb_ovsdb --db-nb-create-insecure-remote=yes --db-nb-addr=<api ip> --db-nb-cluster-local-addr=<api ip>`.
  - For every host except `groups['ovn-nb-db'][0]`: `--db-nb-cluster-remote-addr=<api ip of groups['ovn-nb-db'][0]>`.
  - In other words: always a RAFT cluster, with the first inventory host as the seed. Plaintext TCP, no SSL.
- **ovn-northd** (`ovn-northd.json.j2:2`): `--ovnnb-db={{ ovn_nb_connection }} --ovnsb-db={{ ovn_sb_connection }}`.
  - Those are lists of all DB hosts (`group_vars/all.yml:417-420`).
- **ovn-controller** (`ovn-controller.json.j2:2`): `ovn-controller … tcp:127.0.0.1:{{ ovsdb_port }}`, i.e. the local
  OVSDB on 6640 (`group_vars/all.yml:427`). The SB remote comes from `external_ids:ovn-remote` set in bootstrap.

### 5.5 Handlers (`ansible/roles/ovn/handlers/main.yml`), in definition order

1. `Restart ovn-nb-db container` (2-15): `recreate_or_restart_container`.
2. `Restart ovn-sb-db container` (17-30).
3. `Wait for ovn-nb-db` (32-44).
   - `wait_for api_interface_address:6641`, timeout 60, `until success retries 10 delay 6`.
   - **`listen: "Restart ovn-nb-db container"`**.
4. `Wait for ovn-sb-db` (46-58). Same, with `listen: "Restart ovn-sb-db container"`.
5. `Restart ovn-northd container` (60-73).
6. `Restart ovn-controller container` (75-88).

All handlers have `when: kolla_action != "config"`. There is no `run_once`, `serial` or rolling logic.
- **All NB members restart in the same step, then all SB members.**
- The waits check only that the local TCP port is open. They do not check RAFT membership or leadership.

### 5.6 Bootstrap / registration

- No Keystone, MariaDB or RabbitMQ registration.
- **Cluster creation.** It is implicit, through `ovn-ctl` and the `--db-*-cluster-*` flags.
- **Chassis registration** (`bootstrap.yml`) **re-runs on every deploy, reconfigure and upgrade.**

### 5.7 Dependencies

- **openvswitch role.** It needs the container name `openvswitch_vswitchd`, hard-coded in every bootstrap command
  (`bootstrap.yml:5,12,22,29,34,42`), and the local OVSDB on TCP 6640
  (`ansible/roles/openvswitch/templates/start-ovsdb-server.j2:11`).
- **neutron.** `ml2_conf.ini.j2:39-40` and `neutron_ovn_metadata_agent.ini.j2:16-17` use `ovn_nb_connection` and
  `ovn_sb_connection`.
  - Adding or removing a DB host therefore also needs a neutron reconfigure, and it changes the ovn-northd command
    line (restart on all northd hosts) and `ovn-remote` on every chassis.
- **Shared variables.** `neutron_bridge_name` (`group_vars/all.yml:940`), `tunnel_interface_address` (252),
  `computes_need_external_bridge` (949).

### 5.8 Operationally notable

- **(A) The whole DB cluster restarts at once.** Any change to `ovn-nb-db`/`ovn-sb-db` restarts every member at once
  under serial 0. That covers config.json, i.e. the IP, the first-host seed or the group order, and also an image change
  on upgrade.
  - NOT AVAILABLE: whether RAFT loses quorum, how the neutron-server OVN driver and ovn-northd reconnect, and whether
    the data plane keeps its installed flows while the SB is unreachable.
  - Mitigation: `ANSIBLE_SERIAL` gives a rolling restart, at the cost of making every play serial.
- **(B) Whether the seed host is a single point of failure for re-deploys is NOT AVAILABLE.** The DB on
  `groups[...][0]` gets no `cluster-remote-addr`.
  - NOT AVAILABLE: what ovn-ctl does if that first host is replaced or its `ovn_nb_db`/`ovn_sb_db` volume is lost, in
    particular whether it **creates a new, separate single-node cluster** instead of joining the existing one (split
    brain, with clients load-balancing across two clusters).
  - There is no code for member removal or replacement (`cluster/kick`, `cluster/leave`), and none for backups (grep:
    no `ovsdb-client backup` anywhere in roles).
- **(C) ovn-controller restarts.** They happen on image or container-parameter change (upgrade, `deploy-containers`) or
  when a deploy/reconfigure rewrites its `config.json`, and hit **all computes and network nodes in parallel**. The OVN
  manifests have no `config_files` (`roles/ovn/templates/*.json.j2`), so `kolla_set_configs --check` always exits 0: a
  command-line change written by `genconfig` is applied neither by `deploy-containers` nor by a later run, until the
  container restarts for another reason ([Kolla images
  §3](../../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
  - NOT AVAILABLE: whether Ussuri-era OVN clears and re-installs OpenFlow flows on restart, and so whether there is a
    short data-plane interruption per chassis, plus north-south traffic loss when all gateway chassis (network nodes)
    restart together.
  - NOT AVAILABLE: whether there is also an SB DB reconnect storm whose size scales with the number of computes.
- **(D) Bootstrap cost scales with computes.** It runs 4 `docker exec ovs-vsctl` per compute (5 with
  `computes_need_external_bridge`), counted from the `when` conditions of `bootstrap.yml:2-45` for a compute in the
  default `ovn-controller-compute` and `openvswitch` groups (`inventory/multinode:144-147,792-793`), on every
  deploy, reconfigure and upgrade, always reported as changed.
  - NOT AVAILABLE: whether re-setting identical `external_ids` is a no-op for ovn-controller, and whether a changed
    `ovn_sb_connection` makes every chassis reconnect.
- **(E) Gateway options are clobbered.**
  - `enable-chassis-as-gw` *overwrites* `ovn-cms-options` on network nodes (`bootstrap.yml:27-30`).
  - It is *removed* entirely on non-gateway openvswitch hosts (32-37) on every run.
  - Any manual `ovn-cms-options` value, such as availability-zone hints, is overwritten or removed on every
    reconfigure (the code above). The impact of that loss is NOT AVAILABLE.
  - Bridge mappings are only ever set, never removed (18-25).
- **(F) Security.** NB and SB listen with `create-insecure-remote=yes` on plain TCP.
- **(G) OVN + DPDK cannot work in this release (inference from code):**
  - With `enable_ovs_dpdk` the openvswitch play is skipped (`site.yml:716`).
  - ovs-dpdk containers are only enabled when `neutron_plugin_agent in ['openvswitch']`
    (`ansible/roles/ovs-dpdk/defaults/main.yml:10,24`).
  - OVN bootstrap execs into `openvswitch_vswitchd`.
- **(H) Missing inventory groups are not caught.** There is no group validation precheck. An old inventory without the
  `ovn-*` groups only surfaces as Jinja errors on `groups['ovn-…']`.

---

## 6. `ovs-dpdk` role

### 6.1 Play

`site.yml:723-732`: hosts `openvswitch` ∩ `enable_openvswitch_True_enable_ovs_dpdk_True`, `serial: kolla_serial`,
role tag `ovs-dpdk`.
- `enable_ovs_dpdk: "no"` (`group_vars/all.yml:686`).
- The openvswitch play is mutually exclusive with it (`site.yml:712-721`).
- Default `openvswitch` group = network, compute, manila-share (`inventory/multinode:144-147`).

### 6.2 `ovsdpdk_services` (`ansible/roles/ovs-dpdk/defaults/main.yml:6-35`)

| key | container | mapping | enabled | flags / volumes |
|---|---|---|---|---|
| ovsdpdk-db | `ovsdpdk_db` | `host_in_groups`: compute, manila-share (if enabled), neutron-dhcp-agent, -l3-agent, -metadata-agent (11-18) | `neutron_plugin_agent in ['openvswitch']` | `/run/openvswitch:shared`, named volume `ovsdpdk_db:/var/lib/openvswitch/` (75-81) |
| ovsdpdk-vswitchd | `ovsdpdk_vswitchd` | same expression (26-33) | same | **privileged: True**; **`/lib/modules:ro`, `/run/openvswitch:shared`, `/dev:/dev:shared`** (82-89) |

- Container commands: `start-ovsdb-server 127.0.0.1` and `ovs-vswitchd unix:/run/openvswitch/db.sock … --mlockall`
  (`templates/*.json.j2`).
- `neutron_bridge_name: "br_dpdk"` (56) is a role default.
  - Ansible merges role defaults first and group variables after them (ansible 2.9.27
    `lib/ansible/vars/manager.py:186-190,205-206,290-293`), so it is **shadowed** by playbook
    `group_vars/all.yml:940` (`br-ex`). The role default is dead unless set in globals.
- **Templating bug in `ovs_cidr_mappings`** (44). For multiple bridges it emits the literal text
  `{neutron_bridge_name.split(',')[0]}` (single braces) instead of a Jinja expression.

### 6.3 Task flow

- **deploy** = `config.yml` → `check-containers.yml` → `meta: flush_handlers` (`deploy.yml:2-7`).
- **reconfigure** and **upgrade** = deploy.
- **deploy-containers** = check-containers.
- **precheck** = service-precheck (`precheck.yml:2-6`).
- **check** = empty.
- **config (genconfig)** = **config.yml**. This *includes host-mutating NIC binding* (see below).
- **pull = BUG.**
  - The `vars/main.yml:2` value `project_name: "ovs"` makes `service-images-pull` look up `ovs_services`
    (`ansible/roles/service-images-pull/tasks/main.yml:14`), which does not exist anywhere (grep).
  - For an undefined name and no `default`, the `vars` lookup raises `No variable found with this name: ovs_services`
    (ansible 2.9.27 `lib/ansible/plugins/lookup/vars.py:80-94`).
  - The lookup runs while Ansible builds the `with_dict` loop. The `Pull images` task has no `when` of its own, and
    the role's `when` is true on DPDK hosts (`site.yml:730-732`), so Ansible re-raises that error and the task fails
    on DPDK hosts (ansible 2.9.27 `lib/ansible/executor/task_executor.py:105-109,179-180,566-568`). The end-to-end
    outcome of `kolla-ansible pull` is NOT AVAILABLE.
- **stop** = service-stop with `ovsdpdk_services` (works).

`config.yml` key tasks (all of them run on deploy, reconfigure, upgrade **and genconfig**):
- **Config dirs and config.json** (2-25), gated by `enabled` and `host_in_groups`.
  - The `config.json` copy has **no `become`**, although the dirs are root:root 0770 (`config_owner_user: root`,
    `group_vars/all.yml:20-21`).
  - NOT AVAILABLE: whether this fails with a non-root `ansible_user`.
- **"Copying ovs-dpdkctl tool"** (27-31). `copy src: ../tools/ovs-dpdkctl.sh`. It has no `become` and **no `when`**.
- **"Install ovs-dpdkctl service and config"** (33-44). `command: ovs-dpdkctl.sh install`, which always reports
  changed and has no `when`. Inside `tools/ovs-dpdkctl.sh`:
  - `gen_config` runs **only if the conf file does not exist** (350-353). Later changes to bridge, port or cidr mappings
    in globals are **silently ignored**.
  - `modprobe` of the DPDK driver.
  - Install and enable the `ovs-dpdkctl` systemd unit (`bind_nics` on boot).
  - Rewrite the ifcfg or interfaces file for the bridge every run, and on RedHat start `ovs-dpdk-bridge`
    (`ovs-dpdkctl.sh:218-258, 270-318, 350-367`).
- **"Binds the interface to the target driver"** (46-57). `ovs-dpdkctl.sh bind_nics` unbinds and rebinds the NICs listed
  in `port_mappings` when their current driver differs (`ovs-dpdkctl.sh:116-127`).
  - **This runs even under `kolla-ansible genconfig`.**

### 6.4 Config files

- `/etc/kolla/ovsdpdk-{db,vswitchd}/config.json`, which notify their restart handlers.
- `/etc/kolla/ovsdpdk-db/ovs-dpdkctl.sh` and `/etc/kolla/ovsdpdk-db/ovs-dpdkctl.conf` (generated once).
- Systemd units `/etc/systemd/system/ovs-dpdkctl.service` and `ovs-dpdk-bridge.service`, plus the network ifcfg or
  interfaces file. These notify no handler.
- There are no custom-override paths.

### 6.5 Handlers (`ansible/roles/ovs-dpdk/handlers/main.yml`), in definition order

1. `Restart ovsdpdk-db container` (2-22). It **notifies 6 handlers**: wait db, bridges indexed, **Restart vswitchd**,
   bridges named, wait tunnel ip, gather facts.
2. `Waiting the ovs db service to be ready` (24-34). `docker exec ovsdpdk_db ovs-vsctl --no-wait show`, retries 30 delay
   2.
3. `Ensuring ovsdpdk bridges are properly setup indexed` (36-52). `ovs-dpdkctl.sh init`, only if
   `ovs_physical_port_policy == 'indexed'`.
4. `Restart ovsdpdk-vswitchd container` (54-68).
5. `Ensuring ovsdpdk bridges are properly setup named` (70-86). `init`, when the policy is `named` (the default, line
   54).
6. **`wait for dpdk tunnel ip`** (88-92). `wait_for: host: <dpdk_tunnel_interface_address> timeout: 300 sleep: 5`, with
   **no port and no path**.
   - `wait_for` then just does `time.sleep(timeout)` (ansible 2.9.27
     `lib/ansible/modules/utilities/logic/wait_for.py:538-539`).
   - So **every DB restart costs a fixed 300 s sleep** per batch.
7. `ovs-dpdk gather facts` (94-102). `setup` re-gathers facts.

### 6.6 Bootstrap

OVS DB init (`ovs-dpdkctl.sh init`: `other_config:dpdk-*`, bridges, DPDK ports, `ovs-dpdkctl.sh:164-216`) runs **only
from handlers**, i.e. when `ovsdpdk-db` restarts. It is not re-asserted on a plain reconfigure.

### 6.7 Dependencies

- neutron (openvswitch agent with `ovs_datapath: netdev`, `group_vars/all.yml:715`).
- Hugepages (`ovs_hugepage_mountpoint`).
- `dpdk_tunnel_interface` (defaults to `neutron_external_interface`, `group_vars/all.yml:234`) and its address (254).
- `neutron_plugin_agent == 'openvswitch'`.

### 6.8 Operationally notable

- **Any `ovsdpdk-db` restart also restarts `ovs-vswitchd`.** That means an image change or config.json drift.
  - NOT AVAILABLE: whether this is a data-plane outage for all VMs on that host (vhost-user reconnect).
  - It happens **on all DPDK computes in parallel**, followed by a mandatory 5-minute sleep.
- **NIC rebinding and unit installation run on every deploy, reconfigure, upgrade and genconfig.** They are idempotent
  only as long as the driver already matches.
- **Sticky configuration.** `ovs-dpdkctl.conf` is never regenerated, so mapping changes require deleting it manually.

---

## 7. `service-cert-copy` role

### 7.1 How it is applied

- `import_role: service-cert-copy` from `<role>/tasks/copy-certs.yml` in 52 roles (aodh … zun, plus `common` and
  `haproxy`).
- Usually it is gated with `when: kolla_copy_ca_into_containers | bool or <svc>_enable_tls_backend | bool`, e.g.
  `ansible/roles/keystone/tasks/config.yml:41-43`.
- **haproxy gates only on `kolla_copy_ca_into_containers`** (`ansible/roles/haproxy/tasks/config.yml:128-130`).
- chrony, memcached, ovn and ovs-dpdk do **not** use it.

### 7.2 Tasks (`ansible/roles/service-cert-copy/tasks/main.yml`)

| task (lines) | dest | when | notifies |
|---|---|---|---|
| Copy extra CA certs (2-12) | `/etc/kolla/<item.key>/ca-certificates/` from `{{kolla_certificates_dir}}/ca/` | `kolla_copy_ca_into_containers` | `Restart <item.key> container` |
| Backend TLS cert (14-33) | `/etc/kolla/<item.key>/<project_name>-cert.pem`. first_found: `certificates/<host>/<project>-cert.pem` → `certificates/<host>-cert.pem` → `certificates/<project>-cert.pem` → `kolla_tls_backend_cert` | the service has an enabled haproxy entry with `tls_backend` true | `Restart <item.key> container` |
| Backend TLS key (35-54) | `…/<project_name>-key.pem` (mode 0600), with the same lookup order for `-key.pem` | same | same |

The loop is `with_dict: project_services | select_services_enabled_and_mapped_to_host`
(`kolla_ansible/filters.py:82-91`).

### 7.3 Notable

- **For haproxy, the loop includes `keepalived`.**
  - A CA bundle change (e.g. a root CA rotation with `kolla_copy_ca_into_containers: yes`) therefore triggers
    `Restart keepalived container` on all haproxy hosts in parallel, together with the haproxy restart.
  - Whether that flaps the VIP is NOT AVAILABLE. `keepalived.json.j2` does not reference the CA files.
  - The kolla image does install them: keepalived starts through `kolla_start`, which runs `kolla_copy_cacerts` at every
    start. That script deletes the old `kolla-customca-*` entries and installs every file of
    `/var/lib/kolla/config_files/ca-certificates/` (kolla `docker/base/start.sh:13`, `docker/base/copy_cacerts.sh:7-27`;
    [Kolla images §2.4](../../concepts/kolla-images.md#24-kolla_copy_cacerts-and-kolla_httpd_setup)).
- **A CA or backend cert rotation restarts every container of every service using it** (whole fleet,
  per-play parallel).
- It is a pure file copy, with no expiry check.

---

## 8. `certificates.yml` playbook / `certificates` role

### 8.1 Play

`ansible/certificates.yml:1-8`:
- `import_playbook: gather-facts.yml` with `when: kolla_enable_tls_backend` (to obtain the API IPs of `tls-backend`
  hosts).
- Then `hosts: localhost`, `roles: [certificates]`.
- No serial, no tags, no `become`. It runs from `kolla-ansible certificates` (`tools/kolla-ansible:454-457`).
- The docs call it a "private test Certificate Authority" (`doc/source/admin/tls.rst:65-66`).

### 8.2 Flow (`ansible/roles/certificates/tasks/main.yml:2-6`)

`generate-root.yml` → `generate.yml` → `generate-backend.yml` (when `kolla_enable_tls_backend`).
- **Root CA** (`generate-root.yml`).
  - `root.key` RSA 4096 and `root.crt`, CN=KollaTestCA, **1024 days**, each guarded by `creates:` (14-33).
  - The CA is copied to `{{kolla_certificates_dir}}/ca/root.crt` (41-45). That is the source that
    `service-cert-copy` distributes.
- **External and internal certs** (`generate.yml`).
  - Key, CSR and cert with **365 days**, each `creates:`-guarded.
  - They are assembled into `kolla_external_fqdn_cert` and `kolla_internal_fqdn_cert` (14-80, 82-137).
  - The internal cert is a copy of the external one when the VIPs are the same (70-80).
  - SAN is a single DNS or IP entry from `kolla_{external,internal}_fqdn` (`templates/openssl-kolla*.cnf.j2:15-21`).
- **Backend cert** (`generate-backend.yml`).
  - One shared cert (**500 days**) whose SANs are the API IPs of **all `tls-backend` hosts**
    (`templates/openssl-kolla-backend.cnf.j2:15-18`; `[tls-backend:children] control`, `inventory/multinode:42-43`).
  - Copied to `backend-cert.pem` and `backend-key.pem` (54-64).
- Global paths: `kolla_certificates_dir: "{{ node_config }}/certificates"` (`group_vars/all.yml:799`, normally
  `/etc/kolla/certificates`).

### 8.3 Notable

- **No rotation or renewal.** Every generating step is `creates:`-guarded, so re-running never renews expired
  certificates. External and internal certs expire after 365 days; the files must be deleted manually.
- **Adding a `tls-backend` host does not update the backend SANs.** `backend.csr` and `backend.crt` exist
  (`generate-backend.yml:32,46`), so the cert is not re-issued.
  - NOT AVAILABLE: whether haproxy then rejects the new backend with `kolla_verify_tls_backend: yes`
    (`group_vars/all.yml:804`).
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
| haproxy | any `services.d`/haproxy.cfg/run.sh/pem/CA/config.json change, image change | all haproxy hosts | all APIs plus MariaDB and other VIP traffic; VIP failover: NOT AVAILABLE |
| keepalived | keepalived.conf (inventory order!), config.json, CA copy, image change, **every upgrade (backups stopped)** | all haproxy hosts | VIP move or outage: NOT AVAILABLE |
| memcached | config.json (IP, port, memory, limit), image | all memcached hosts | whether all caches are emptied and Horizon users logged out: NOT AVAILABLE |
| chrony | chrony.conf (VIP, NTP servers, chrony-server membership), image | all hosts incl. computes | low |
| ovn-nb/sb-db | config.json (IPs, seed host = `groups[...][0]`), image | all DB hosts | NB/SB API down; quorum re-election: NOT AVAILABLE |
| ovn-northd | NB/SB host list, image | all northd hosts | logical-flow processing pause |
| ovn-controller | image, drift | **all computes and network nodes** | data-plane blip per chassis: NOT AVAILABLE |
| ovsdpdk-db → vswitchd | image, drift (db restart always restarts vswitchd) | **all DPDK hosts** | VM data-plane outage: NOT AVAILABLE; then a 300 s sleep |

Things that run on **every** reconfigure, regardless of changes:
- haproxy config-host (sysctl/modprobe) and the template set, plus 49 service includes (`-t haproxy` or no tags).
- OVN bootstrap `ovs-vsctl` (per chassis).
- ovs-dpdk `install` + `bind_nics` (per DPDK host, **also on genconfig**).
- `compare_container` with a `docker exec kolla_set_configs --check` for every container on every host.

Things whose cost scales with the number of computes: chrony, ovn-controller config + bootstrap, ovs-dpdk. haproxy,
memcached, the OVN DB and certificates scale only with control or haproxy hosts.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
