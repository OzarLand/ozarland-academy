---
title: Fact sheet B
description: "Fact sheet for MariaDB, RabbitMQ and Keystone in Kolla-Ansible 2025.1: Galera bootstrap, recovery, backup and rolling restart, RabbitMQ, Keystone fernet keys."
tags: [mariadb, rabbitmq, keystone, mariadb-backup, mariadb-recovery, handlers]
---

# Fact sheet B

Source: `kolla-ansible` at tag `2025.1-eom` (commit `7222f0f`), the kolla image repository at tag `2025.1-eom` (commit
`c4b53a2`) and ansible-core 2.18.20. Kolla-Ansible paths are relative to `ansible/` unless they start with
`kolla_ansible/`, `etc/`, `releasenotes/` or `doc/`.
Labels: **FACT** = read directly from source code (cited): kolla-ansible, the kolla image repository (cited as kolla
`docker/...`) or Ansible (cited as ansible-core 2.18.20 `lib/ansible/...`). **NOT AVAILABLE** = these sources do not
establish it, often because it depends on upstream MariaDB, ProxySQL, RabbitMQ, Keystone, HAProxy, Docker or Podman
behaviour that is not in them. The points marked NOT AVAILABLE are to be confirmed by the community.

The supported Ansible range is ansible-core 2.17 to 2.18 (`roles/prechecks/vars/main.yml:4-5`). Statements about
handler, serial and include semantics cite the ansible-core 2.18.20 source; ansible-core 2.17 is NOT AVAILABLE.

**What changed since 2024.1, in one paragraph (FACT):** the play structure is the same: MariaDB and RabbitMQ are applied
by their own playbooks, which `site.yml` imports (`site.yml:415,483`), the role handlers only fill `group_by` groups and
separate plays restart them in `serial: "33%"` batches (`mariadb.yml:1-92`, `rabbitmq.yml:1-70`). **Who decides a
restart changed:** no config task notifies any more; each role's `check-containers.yml` imports
`service-check-containers`, which compares every container and notifies `Restart <key> container` only for the ones
reported changed (`roles/service-check-containers/tasks/main.yml:4-41`). **ProxySQL is the default database load
balancer** (`enable_proxysql: "yes"`, `group_vars/all.yml:958`), so by default there is no `mariadb_clustercheck`
container, the shard root user is `root_shard_0` and `upgrade` removes an existing `mariadb_clustercheck`
(`roles/mariadb/defaults/main.yml:132,137`; `roles/mariadb/tasks/upgrade.yml:2-9`). The MariaDB WSREP checks and the
post-deploy check now go through `kolla_toolbox mysql_query` to the node itself instead of `mysql` on the command line
through the VIP, and `galera.cnf` gains a 2 GB `innodb_log_file_size` (`roles/mariadb/tasks/check.yml:6-22`;
`roles/mariadb/templates/galera.cnf.j2:61`). **RabbitMQ classic mirrored queues are gone:** quorum queues, transient
quorum queues and stream fanout are always on, and the `om_enable_rabbitmq_*` switches are removed
(`roles/keystone/templates/keystone.conf.j2:62-77`; `group_vars/all.yml:292`). The default RabbitMQ image moves from 3.13
to 4.0 (kolla `docker/rabbitmq/rabbitmq/rabbitmq_packages_rpm.rocky:1-4`). Keystone keeps its handler order, gains an
HTTP health check in HAProxy and a `check.yml`, and every service's `www_authenticate_uri` now points at the public
Keystone URL. The CLI is the Python `kolla_ansible/cli/commands.py`: the commands are `mariadb-backup`,
`mariadb-recovery` and `rabbitmq-reset-state`, and there is no `rabbitmq-upgrade` command any more
(`setup.cfg:71-73`).

---

## 0. Shared context that applies to all three roles

| Topic | Fact | Evidence |
|---|---|---|
| Action dispatch | `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"`. mariadb first puts every `mariadb` host into its shard group (`mariadb_shard_<id>` via `add_host`, shard 0 by default); rabbitmq adds `when: inventory_hostname in groups[role_rabbitmq_groups]` | `roles/mariadb/tasks/main.yml:2-9`, `group_vars/all.yml:549-553`, `roles/keystone/tasks/main.yml:2`, `roles/rabbitmq/tasks/main.yml:2-3` |
| `common` dependency | None. The three roles have no `meta/` directory. `common` is its own play, tagged `common` (`site.yml:88-103`), so it runs only in an untagged run or with `-t common` | `ls roles/{mariadb,rabbitmq,keystone}` (no `meta`) |
| `common_run` guard | Still absent: no `common_run` anywhere in `ansible/`. The `mariadb-recovery` and `mariadb-backup` commands run playbooks that contain only the mariadb role (`mariadb_recovery.yml:1-13`, `mariadb_backup.yml:1-11`), so `common` does not run. The CLI passes `kolla_action=deploy` for recovery and `kolla_action=backup -e mariadb_backup_type=...` for backup | `kolla_ansible/cli/commands.py:437-481` |
| Serial | The CLI sets `kolla_serial` only for `reconfigure` and `upgrade`, and **only to the constant `ANSIBLE_SERIAL = 0`**, after the user's `-e`, so neither action can be batched ([F19](../findings.md#f19)). Other actions leave it unset. The MariaDB and RabbitMQ restart plays ignore it anyway: they use a fixed `serial: "33%"` | `kolla_ansible/cli/commands.py:22,136,278`; `mariadb.yml:24,42`; `rabbitmq.yml:36` |
| `max_fail_percentage` | Every play of the three playbooks, and the keystone play, sets `max_fail_percentage: {{ <svc>_max_fail_percentage \| default(kolla_max_fail_percentage) \| default(100) }}`. With the default 100 it never stops a play early: ansible-core breaks the play only when the failed hosts of the current batch exceed that share of the batch size, and it clears the failed-host list before each batch | `mariadb.yml:8-11,25-28,43-46,59-62,75-78`; `rabbitmq.yml:8-11,37-40,56-59`; `mariadb_recovery.yml:4-7`; `mariadb_backup.yml:4-7`; `site.yml:504-507`; ansible-core 2.18.20 `lib/ansible/plugins/strategy/linear.py:335-349`, `lib/ansible/executor/task_queue_manager.py:322-334` |
| Who notifies a restart | **Changed in 2025.1.** Config tasks have no `notify`. `check-containers.yml` = `import_role: service-check-containers`, which runs `compare_container` for each enabled, mapped service and then notifies `Restart <key> container` for each changed one; the handlers lost their `kolla_action != "config"` guard, since `genconfig` no longer notifies anything | `roles/mariadb/tasks/check-containers.yml:2-3`, `roles/rabbitmq/tasks/check-containers.yml:2-3`, `roles/keystone/tasks/check-containers.yml:2-3`; `roles/service-check-containers/tasks/main.yml:4-41` |
| What `compare_container` sees | Parameters (image, volumes, environment, healthcheck, labels, command, ...) and, through `kolla_set_configs --check` inside the running container, the files listed in `config.json` and the command. Any non-zero `--check` exit other than 137 is an error, exit 1 is "changed"; every `set_configs.py` error class uses exit 1 | `roles/service-check-containers/tasks/main.yml:8-26`; `module_utils/kolla_docker_worker.py:146-181`; kolla `docker/base/set_configs.py:41-44,63-68,233-255` |
| Config strategy | `config_strategy: "COPY_ALWAYS"`, so `recreate_or_restart_container` restarts the container when its parameters are unchanged, and recreates it when they differ | `group_vars/all.yml:49`; `module_utils/kolla_docker_worker.py:352-374` |
| Graceful stop | Effective stop timeout is **60 s** (`docker_graceful_timeout`), passed through `docker_common_options` (`library/kolla_container.py:311,357-389`; `group_vars/all.yml:148,160`). With Docker, a container with a systemd unit is stopped and restarted through that unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_docker_worker.py:450-470`; `module_utils/kolla_systemd_worker.py:33`). For MariaDB the image still runs `dumb-init` without `--single-child`, and its comment says that mysqld_safe ignores SIGTERM and that TERM is then sent to all subprocesses, including mysqld (kolla `docker/mariadb/mariadb-server/Dockerfile.j2:65-76`). NOT AVAILABLE: the dumb-init and mysqld_safe behaviour itself, and so whether mysqld shuts down cleanly within the 60 s | `group_vars/all.yml:148` |
| Bootstrap containers | `kolla_container` defaults `remove_on_exit: True`, so `detach: False` bootstrap/upgrade containers are stopped and removed after they exit. With Docker they use `restart_policy: oneshot` and get no systemd unit. Containers started with a `BOOTSTRAP` label are later recreated because `compare_labels` sees a difference | `library/kolla_container.py:312`; `module_utils/kolla_docker_worker.py:349-350,391-393,416-418`; `module_utils/kolla_container_worker.py:167-179` |
| `compare_environment` | Checks only that the *desired* env keys exist with equal values. Extra env vars on the running container (for example `BOOTSTRAP_ARGS`) are not detected; labels are what force the recreate | `module_utils/kolla_container_worker.py:304-315` |
| First 2025.1 check | The systemd unit template changed again (`PartOf=kolla.target`) and the unit text is part of `compare_container`, so the first 2025.1 check of a container whose unit 2024.1 wrote reports it as changed ([F16](../findings.md#f16)). For MariaDB and RabbitMQ that notification only fills the restart groups, so the restart is batched by the restart plays; for Keystone it restarts the containers through the handlers (3.5) | `module_utils/kolla_systemd_worker.py:155-168`; `module_utils/kolla_container_worker.py:58-65` |
| Handler order | Ansible runs handlers in the order they are **defined in `handlers/main.yml`**, not in notify order: at a flush each host walks a copy of the play's handler list and runs those it was notified for. Under the default `linear` strategy each handler is queued on every notified host before the results are awaited. This matters for the keystone handlers and for the order in which the mariadb `group_by` handlers fill their groups | ansible-core 2.18.20 `lib/ansible/executor/play_iterator.py:193-198,424-443`, `lib/ansible/plugins/strategy/linear.py:126,195,216` |
| Loadbalancer config | The loadbalancer play (`site.yml:105-327`; hosts `loadbalancer` + `&enable_loadbalancer_True`, `serial: kolla_serial`) runs `include_role ... tasks_from: loadbalancer` for each service. `loadbalancer-config` now renders the HAProxy fragment and, with `enable_proxysql`, the ProxySQL users and rules of the service | `site.yml:105-110`; `roles/loadbalancer-config/tasks/main.yml:2-8` |
| Batch semantics of `serial: "33%"` | The batch size is `int(0.33 × N)`, at least 1, where N is the number of hosts the restart play targets: 1 host per batch up to 6 hosts, 2 for 7 to 9, 3 for 10 to 12. If every host of a batch fails, the playbook stops and later batches do not run; if only some fail, the next batch runs (with the default `max_fail_percentage` of 100) | ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:179-204,269-309`, `lib/ansible/utils/helpers.py:23-32` |

Play order in `site.yml` (relevant subset): loadbalancer `:105` -> valkey `:399` -> **mariadb** (`import_playbook:
mariadb.yml`, `:415`) -> memcached `:417` -> **rabbitmq** (`import_playbook: rabbitmq.yml`, `:483`) -> etcd `:485` ->
**keystone `:498`** -> everything else (opensearch `:512`, glance `:542` onward). Keystone therefore still runs after its
DB, cache and MQ dependencies, and before every service that registers with Keystone.

---

## 1. MariaDB (`ansible/roles/mariadb`)

### 1.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial | Notes |
|---|---|---|---|---|---|
| `Apply role loadbalancer` -> `include_role mariadb tasks_from: loadbalancer` | `site.yml:223-227` | `loadbalancer` + `&enable_loadbalancer_True` (`:105-110`) | `mariadb` | loadbalancer play has `serial: kolla_serial` (`:110`) | `when: enable_mariadb or enable_external_mariadb_load_balancer`. Ensures the monitor user (`monitor` with ProxySQL, the default; `haproxy` otherwise) on the first host of each shard, `run_once`, `failed_when: False`, now with `USAGE,REPLICATION CLIENT` (`roles/mariadb/tasks/loadbalancer.yml:18-40`; `group_vars/all.yml:545`) |
| `Apply role mariadb` | `mariadb.yml:3-16` | `mariadb` + `&enable_mariadb_True` | `mariadb` | **none** | `gather_facts: false` (facts come from `gather-facts.yml`, `site.yml:2`) |
| `Restart mariadb services` | `mariadb.yml:18-34` | `mariadb_restart` + `&enable_mariadb_True` | `mariadb` | **`"33%"`** | runs `restart_services.yml` on the hosts that handler 5 grouped (1.5) |
| `Start mariadb services` | `mariadb.yml:36-52` | `mariadb_start` + `&enable_mariadb_True` | `mariadb` | **`"33%"`** | same task file, hosts grouped by handler 6 |
| `Restart bootstrap mariadb service` | `mariadb.yml:54-68` | `mariadb_bootstrap_restart` + `&enable_mariadb_True` | `mariadb` | none | the first-bootstrap host only (handler 4) |
| `Apply mariadb post-configuration` | `mariadb.yml:70-92` | `mariadb` + `&enable_mariadb_True` | `mariadb` | none | `post-deploy.yml` (`register.yml`, `check.yml`) for deploy/reconfigure/upgrade; `post-upgrade.yml` for upgrade |
| `Recover mariadb` | `mariadb_recovery.yml:1-13` | `mariadb` (no `enable_` intersection) | `mariadb` | none | play var `mariadb_recover: true`; role `when: enable_mariadb`. Sets no `gather_facts`, so the implicit fact gathering applies (ansible-core 2.18.20 `lib/ansible/executor/play_iterator.py:283-298`). The CLI (`kolla-ansible mariadb-recovery`) passes `kolla_action=deploy` (`kolla_ansible/cli/commands.py:470-481`). The playbook has no restart plays |
| `Backup MariaDB` | `mariadb_backup.yml:1-11` | `mariadb` | `mariadb` | none | role `when: enable_mariabackup`. The CLI (`kolla-ansible mariadb-backup`, `--full` by default or `--incremental`) passes `kolla_action=backup` and `mariadb_backup_type` (`kolla_ansible/cli/commands.py:437-467`) |

Every play of the table also sets `max_fail_percentage` (section 0). **2024.1 form:** `mariadb_recovery` and
`mariadb_backup` with underscores; `setup.cfg:72-73` registers only the hyphenated names.

**What the absence of `kolla_serial` means (FACT plus reasoning):**
- `kolla_serial` is still **ignored** for MariaDB. The role play handles all mariadb hosts in one batch, and the restart
  plays use their own `serial: "33%"`.
- This is required by the design. `lookup_cluster.yml` uses `group_by` and the `mariadb_shard_<id>_*` groups across the
  whole cluster in one pass (port liveness, WSREP state, volume existence) to decide bootstrap, fail-fast and which
  hosts are restarted or started (`roles/mariadb/tasks/lookup_cluster.yml:2-81`). Under serial these groups would only
  describe the current batch.
- Rolling behaviour comes from the **restart plays** (`serial: "33%"`, see 1.5), not from the handlers.
- `--limit` still narrows the plays: Ansible applies the limit when it resolves a play's hosts (ansible-core 2.18.20
  `lib/ansible/executor/playbook_executor.py:276`, `lib/ansible/inventory/manager.py:403-405`), and a `group_by` group
  only receives the hosts that ran the task (`lib/ansible/plugins/action/group_by.py:43-51`,
  `lib/ansible/plugins/strategy/__init__.py:684-686`). Group-derived decisions then only see the limited hosts (for
  example `mariadb_cluster_exists` is computed from `groups[mariadb_shard_group + '_had_volume_True']` among play
  hosts). The "existing but stopped" check uses the full shard length `groups[mariadb_shard_group] | length > 1`, filled
  by `add_host` from `groups['mariadb']` (`roles/mariadb/tasks/main.yml:2-7`, `lookup_cluster.yml:36-43`). FACT from these lines:
  `--limit` to a single new node on an existing cluster makes that node treat the cluster as new
  (`mariadb_cluster_exists=false`, `lookup_cluster.yml:11-18`), so in the `Start mariadb services` play it waits for
  WSREP Synced with only a 60 s budget (`restart_services.yml:31-53`).

### 1.2 `mariadb_services` (`ansible/roles/mariadb/defaults/main.yml:2-47`)

In 2025.1 the dict spans `roles/mariadb/defaults/main.yml:2-53`, as in 2024.1 (the heading keeps its earlier range so
that links stay stable).

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `mariadb` | `mariadb` | `{{ mariadb_shard_group }}` (`mariadb_shard_0` by default) | `true` | Image `<prefix>mariadb-server` (`:70`). Volumes: `/etc/kolla/mariadb`, `mariadb_datadir_volume:/var/lib/mysql` (default `mariadb`, `group_vars/all.yml:547`), `kolla_logs` (`:81-86`). Environment `MYSQL_USERNAME` (monitor user), `MYSQL_PASSWORD` (the monitor password with ProxySQL, otherwise empty), `MYSQL_HOST`, `AVAILABLE_WHEN_DONOR=1` (`:11-15`). Container healthcheck `/usr/bin/clustercheck` when healthchecks are enabled (`:96-107`; the image fetches that script, kolla `docker/mariadb/mariadb-base/Dockerfile.j2:27-34`). HAProxy `mariadb` (internal, enabled unless external LB): `mode tcp`, client/server timeouts 3600 s, `option httpchk` when clustercheck is enabled (`:16-29`). `custom_member_list` = `internal_haproxy_members`, where **only the first host of the default shard is active and every other host is `backup`** (`:64`). **Changed in 2025.1, by default this HAProxy entry is not used:** with `enable_proxysql` (now `yes`, `group_vars/all.yml:958`) ProxySQL is the database load balancer (`mariadb_loadbalancer`, `group_vars/all.yml:554`), and the loadbalancer role removes `services.d/mariadb.cfg` ([fact sheet A, 1.4](a-infra-lb-ovn.md#14-config-files-generated-ansibleroleshaproxytasksconfigyml)) |
| `mariadb-clustercheck` | `mariadb_clustercheck` | `{{ mariadb_shard_group }}` | `enable_mariadb_clustercheck` | **Changed in 2025.1:** the default is set in the role, `'True' if mariadb_loadbalancer == 'haproxy' else 'False'` (`:132`), so the container is **off by default** (ProxySQL). When on, same environment as above (`:49-53`), and the command is now `socat_wrapper ... tcp-l:4569 ... EXEC:clustercheck` (`roles/mariadb/templates/mariadb-clustercheck.json.j2:2`) |

Other defaults: `database_max_timeout: 120` (`:59`); `mariadb_service: "{{ mariadb_services['mariadb'] }}"` is used by
recovery (`:112`); recovery temp file `/tmp/kolla_mariadb_recover_inventory_name_<shard>` (`:113`);
`mariadb_backup_host: "{{ groups[mariadb_shard_group][0] }}"` (`:123`); backup schema `mysql` (`:124`); backup user
`backup` in HAProxy mode, `backup_shard_<id>` with ProxySQL (`:125`; `group_vars/all.yml:557`); shard root user
`database_user` in HAProxy mode, `root_shard_<id>` with ProxySQL (`:137`; `group_vars/all.yml:556`). Ports: 3306, wsrep
4567, IST 4568, SST 4444, clustercheck 4569 (`group_vars/all.yml:91,538-542`). `enable_mariabackup: "no"`
(`group_vars/all.yml:922`). **New in 2025.1:** `mariadb_innodb_log_file_size_mb: 2048` (`group_vars/all.yml:564`), and
`mariadb_backup_target` (`active` with HAProxy, `replica` with ProxySQL, `group_vars/all.yml:555`), which no file of the
2025.1 tree reads (grep finds only its definition) (1.8, item 13).

### 1.3 Task flow per `kolla_action`

| Action | Task files (in order) | Key behaviour |
|---|---|---|
| **deploy** | role play: `deploy.yml`: `config.yml` -> `check-containers.yml` -> `recover_cluster.yml` [only with `migration_flag`, see below] -> `bootstrap.yml` (= `lookup_cluster.yml` -> `bootstrap_cluster.yml` [only if no cluster and host is `groups[mariadb_shard_group][0]`] -> `recover_cluster.yml` [only if `mariadb_recover`]); handlers at the end of the play. Then the restart, start and bootstrap-restart plays, then post-configuration: `register.yml` -> `check.yml` | `roles/mariadb/tasks/deploy.yml:1-11`, `bootstrap.yml:1-10`, `post-deploy.yml:1-4`; `mariadb.yml:3-86` |
| **reconfigure** | `import_tasks: deploy.yml` (identical to deploy) | `roles/mariadb/tasks/reconfigure.yml:2` |
| **upgrade** | role play: `upgrade.yml` = **new in 2025.1:** stop and remove `mariadb_clustercheck` when ProxySQL is the load balancer (`ignore_missing`), then `deploy.yml`; restart plays; post-configuration: `post-deploy.yml`, then **"Run upgrade in MariaDB container"** (`upgrade_mariadb`, `KOLLA_UPGRADE`, `DB_HOST=api_interface_address`, `DB_PORT`, `detach: False`) on **every** mariadb host, in a play without `serial`, with no `run_once` and no image-changed condition. The image appends the `mysql_upgrade` output to `mariadb-upgrade.log` (kolla `docker/mariadb/mariadb-server/extend_start.sh:47-57`) | `roles/mariadb/tasks/upgrade.yml:1-11`, `roles/mariadb/tasks/post-upgrade.yml:1-24`; `mariadb.yml:70-92` |
| **deploy-containers** | `check-containers.yml` -> `lookup_cluster.yml` (prerequisite for the handlers; comment `# handlers prerequisite`). Handlers at the end of the role play, then the restart plays. No post-configuration (`when` lists deploy/reconfigure/upgrade only) | `roles/mariadb/tasks/deploy-containers.yml:1-5`; `mariadb.yml:86` |
| **pull** | `service-images-pull` (pulls `mariadb` and `mariadb-clustercheck` if enabled) | `roles/mariadb/tasks/pull.yml` |
| **stop** | `service-stop`: `stop_container` for each enabled, mapped service **on all hosts at once**, unless the name is in `skip_stop_containers` | `roles/mariadb/tasks/stop.yml`, `roles/service-stop/tasks/main.yml:2-14` |
| **precheck** | `service-precheck` (inventory group exists) plus free-port checks for 3306/4567/4568/4444, only if no `mariadb` container is listed | `roles/mariadb/tasks/precheck.yml:1-56` |
| **check** | **New in 2025.1:** `kolla-ansible check` exists again (`kolla_ansible/cli/commands.py:495`). `check.yml` = `service-check` (fails if a container of the role is missing, not running or `unhealthy`), then a `kolla_toolbox mysql_query` `SHOW DATABASES;` as `database_user` to the host's **own** `api_interface_address` on port 3306, 6 retries x 10 s. The task is still named "Wait for MariaDB service to be ready through VIP", but no longer goes through the VIP. It runs on **every** mariadb host (the default-shard restriction is gone), in post-configuration and at the end of recovery | `roles/mariadb/tasks/check.yml:1-22`; `roles/service-check/tasks/main.yml:3-40`; `recover_cluster.yml:237` |
| **config** (genconfig) | `config.yml`. Nothing notifies, so nothing restarts | `roles/mariadb/tasks/config.yml:1-73` |
| **backup** | `backup.yml`: one-shot `mariabackup` container (`detach: False`, `remove_on_exit: True`) on `mariadb_backup_host` only (and only if `mariadb_backup_possible`), using the image of the running `mariadb` container when there is one, mounting `mariadb:/var/lib/mysql` and `mariadb_backup:/backup` and running `kolla_set_configs && /usr/local/bin/kolla_mariadb_backup.sh` with `BACKUP_TYPE` | `roles/mariadb/tasks/backup.yml:1-36`; `roles/mariadb/defaults/main.yml:127` |
| **recovery** (`mariadb-recovery`) | `kolla_action=deploy` with `mariadb_recover=true`, so `deploy.yml` runs and `bootstrap.yml` includes `recover_cluster.yml`. The port and WSREP block of `lookup_cluster.yml` is **skipped** (`when: not mariadb_recover`). `mariadb_recovery.yml` has no restart and no post-configuration plays, so `register.yml` does not run; `recover_cluster.yml` ends with `check.yml` | `lookup_cluster.yml:81`, `bootstrap.yml:9-10`, `recover_cluster.yml:237`; `mariadb_recovery.yml:1-13` |
| **migrate-container-engine** | **New in 2025.1.** `kolla-ansible migrate-container-engine` runs `site.yml` with `kolla_action: deploy` and `migration_flag` (`migrate-container-engine.yml:12-17`). `deploy.yml` then imports `recover_cluster.yml` with `mariadb_cluster_exists: true` **before** `bootstrap.yml`, and `lookup_cluster.yml` skips its `create_volume` (`deploy.yml:6-9`; `lookup_cluster.yml:2-9`). So every MariaDB container is stopped and the cluster is rebuilt from the largest seqno under the new engine, as in a recovery (1.3, Recovery). NOT AVAILABLE: what the `container-engine-migration` role does to the volumes before that | `migrate-container-engine.yml:1-21` |

#### `lookup_cluster.yml` (runs on deploy, reconfigure, upgrade and deploy-containers)

1. `create_volume mariadb`, unless `migration_flag` is set. If the volume already existed (not changed), the host joins
   group `mariadb_shard_<id>_had_volume_True` (`:2-14`).
2. `mariadb_cluster_exists = groups[mariadb_shard_group + '_had_volume_True'] is defined` (`:16-18`).
3. Unless recovering: `wait_for` port 3306 with `search_regex: MariaDB`, `timeout: 10`, `ignore_errors`, then
   `group_by mariadb_shard_<id>_port_alive_{True,False}` (`:20-34`).
4. **Fail fast** with "MariaDB cluster exists but is stopped. Please start it using kolla-ansible mariadb-recovery" if
   the shard has more than one node, the cluster exists and no node is alive (`:36-43`).
5. On alive nodes, `kolla_toolbox mysql_query` `SHOW STATUS LIKE "wsrep_local_state_comment"`, then
   `group_by mariadb_shard_<id>_sync_status_<state>` (`:45-71`).
6. **Fail fast** with "MariaDB cluster is not synced" unless *every* alive node is `Synced` (`:73-79`). So a reconfigure
   refuses to run while any node is Donor or Joining.

With `migration_flag`, step 1 is skipped and `mariadb_volume` stays undefined; `mariadb_volume is not changed` is then
true, so every host lands in `_had_volume_True` (`:9,13`). NOT AVAILABLE: whether that is the intent; it is what the
expression gives.

#### First bootstrap (`bootstrap_cluster.yml`)

- On `groups[mariadb_shard_group][0]` only, when no host had a volume: run `bootstrap_mariadb` (`KOLLA_BOOTSTRAP`,
  `DB_ROOT_PASSWORD`, `DB_MAX_TIMEOUT`), `detach: False`, notify **`Bootstrap MariaDB cluster`**, and
  `set_fact bootstrap_host` (`roles/mariadb/tasks/bootstrap_cluster.yml:1-27`).

#### Recovery (`recover_cluster.yml`), in order

1. Fail if no cluster volume exists ("MariaDB cluster was not found. Is your inventory correct?") (`:2-5`).
2. Delete every `/tmp/kolla_mariadb_recover_inventory_name_*` file on the **controller** (`delegate_to: localhost`,
   `run_once`, `with_fileglob`) (`:7-16`).
3. The following block is skipped if `mariadb_recover_inventory_name` is supplied with `-e`, which lets the operator
   force the bootstrap host (`:95-96`):
   - **Stop the `mariadb` container on every host** (`:19-25`), `ignore_missing`. This happens even if some nodes are
     healthy, so running recovery on a partially-up cluster causes a full DB outage.
   - Run `mariadb_wsrep_recovery` with `BOOTSTRAP_ARGS=--wsrep-recover`, `detach: false` (`:29-43`).
   - Copy `<container_engine_volumes_path>/kolla_logs/_data/mariadb/mariadb.log` to `/tmp/mariadb_tmp.log` on the host,
     take the seqno of the last `Recovered position` line in the whole file with `awk` (`:45-54`), and delete the copy
     (`:56-62`). `seqno = stdout_lines[0]` (`:64-67`). The path follows the engine (`group_vars/all.yml:167`). NOT
     AVAILABLE: whether an empty parse makes that host fail and so drops it from the play.
   - Each host compares its seqno against every other host of its shard, using a bash regex guard. A host with **no
     larger peer** writes its own name to the controller temp file of its shard (`:69-89`). On a tie, every tied host
     writes and the last writer wins (harmless when the seqnos are equal).
   - Every host reads the chosen name with `lookup('file', ...)` (`:91-94`).
4. `bootstrap_host = mariadb_recover_inventory_name` (`:98-100`). On that host,
   `lineinfile grastate.dat safe_to_bootstrap: 1`, editing the volume path on the host directly (`:102-112`).
5. On the bootstrap host: start a `mariadb` container with `BOOTSTRAP_ARGS: --wsrep-new-cluster`, label `BOOTSTRAP` and
   `restart_policy: oneshot` -> wait for the port -> `<engine> exec mariadb mariadb -uroot -p... -e "SET GLOBAL
   wsrep_provider_options='pc.bootstrap=yes'"` (`no_log`) -> wait, through `kolla_toolbox mysql_query`, for
   `wsrep_evs_state` to report `OPERATIONAL` (10 x 6 s) (`:114-173`). **Changed in 2025.1:** the client is `mariadb`
   instead of `mysql` (`:149`).
6. **"Restart slave MariaDB container(s)"**: `start_container` on all other hosts **at once**, then waits only for the
   **port**, not for WSREP Synced (`:175-204`).
7. **"Restart master MariaDB container(s)"**: `recreate_or_restart_container` on the bootstrap host (drops the bootstrap
   args and label), then waits for the port (`:206-235`). Finally `check.yml` (`:237`).
8. Handlers notified by `check-containers` do nothing for `Restart mariadb container`: they need the `_port_alive_*`
   groups, which recovery never creates (`roles/mariadb/handlers/main.yml:59-74`), and `mariadb_recovery.yml` has no restart plays
   anyway. Handler 7 (`Restart mariadb-clustercheck container`) still runs on the hosts it was notified on
   (`roles/mariadb/handlers/main.yml:76-90`).

### 1.4 Config files generated (`ansible/roles/mariadb/tasks/config.yml`)

**Changed in 2025.1:** no task of `config.yml` notifies. A changed file reaches the containers only through the compare
of `check-containers.yml` (section 0), which reads the files listed in `config.json`.

| Destination (`/etc/kolla/...`) | Source / merge order | Seen by the compare | Lines |
|---|---|---|---|
| `mariadb/`, `mariadb-clustercheck/` dirs | (directory), only for enabled, mapped services | n/a | `:2-10` |
| `mariabackup/` dir | only if `enable_mariabackup` and the host is `mariadb_backup_host` | n/a | `:12-22` |
| `mariabackup/my.cnf` | `merge_configs`: `roles/mariadb/templates/backup.my.cnf.j2` + `/etc/kolla/config/backup.my.cnf` + `/etc/kolla/config/mariadb/<host>/backup.my.cnf`. **Changed in 2025.1:** the template contains backup user/password and `host={{ api_interface_address }}`, `port={{ mariadb_port }}`, i.e. the backup host itself instead of the VIP | no (one-shot container) | `:24-37`; `roles/mariadb/templates/backup.my.cnf.j2:1-6` |
| `<svc>/config.json` (both services) | `roles/mariadb/templates/{mariadb,mariadb-clustercheck}.json.j2`. **Changed in 2025.1:** the `mariadb` command is `/usr/bin/mariadbd-safe` (was `mysqld_safe`), and with `database_enable_tls_backend` the CA, certificate and key are copied to `/etc/mariadb/certs/` (`roles/mariadb/templates/mariadb.json.j2:3,11-29`). `mariadb.json.j2` still recursively chowns `/var/log/kolla/mariadb` and `/var/lib/mysql` on every `COPY_ALWAYS` start, the bootstrap, upgrade and `--wsrep-recover` one-shots included (`roles/mariadb/templates/mariadb.json.j2:31-43`; [Kolla images §5.4](../../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)) | yes (file and command) | `:39-45` |
| `mariabackup/config.json` | `roles/mariadb/templates/mariabackup.json.j2` | no | `:47-57` |
| `mariadb/galera.cnf` | `merge_configs`: `roles/mariadb/templates/galera.cnf.j2` + `/etc/kolla/config/galera.cnf` + `/etc/kolla/config/mariadb/<host>/galera.cnf` | yes | `:59-71` |
| certificates | **New in 2025.1:** `copy-certs.yml` = `service-cert-copy` when `database_enable_tls_backend`, which is on only with ProxySQL and `kolla_enable_tls_backend` (`group_vars/all.yml:94`) | yes, when listed in `config.json` | `:73`; `roles/mariadb/tasks/copy-certs.yml:2-7` |

`wsrep-notify.sh` and the clustercheck xinetd file are still not generated (`roles/mariadb/templates/`).

Notable `galera.cnf.j2` contents:
- `wsrep_cluster_address=gcomm://` lists **all** hosts of the shard group when there are two or more, and is empty on a
  single node (`:33`). Adding or removing a DB node therefore changes galera.cnf on every node of the shard, which
  triggers a batched restart of the whole shard.
- `innodb_buffer_pool_size` is 40 % of `ansible_facts.memtotal_mb`, capped at 8192M (`:54-59`). The file depends on
  facts, so a RAM change causes a restart.
- **New in 2025.1:** `innodb_log_file_size = '2048M'` by default (`:61`; `group_vars/all.yml:564`), the TLS lines when
  `database_enable_tls_backend` (`:14-18`), and `mariadb_wsrep_extra_provider_options` appended to
  `wsrep_provider_options` (`:35`).
- `wsrep_sst_method=mariabackup` and `wsrep_sst_auth={{ database_user }}:{{ database_password }}` (root credentials)
  (`:2,44-45`); `max_connections=10000` (`:49`). There is no `wsrep_notify_cmd`.

**First 2025.1 run (FACT plus reasoning):** the 2024.1 `galera.cnf` had no `innodb_log_file_size` and the 2024.1
command was `mysqld_safe`, so the compare reports every `mariadb` container changed on the first 2025.1 run that renders
these files, besides the unit drift of section 0. On `upgrade` the image changes anyway. The restart is the batched one
of 1.5. NOT AVAILABLE: how long MariaDB takes to start with a changed redo log size, and the disk it uses.

### 1.5 Handlers (`ansible/roles/mariadb/handlers/main.yml`), in definition order

| # | Name | listen | Action / logic | Lines |
|---|---|---|---|---|
| 1 | Starting first MariaDB container | `Bootstrap MariaDB cluster` | `start_container mariadb` with `BOOTSTRAP_ARGS: --wsrep-new-cluster`, label `BOOTSTRAP`, `restart_policy: oneshot` | `:2-20` |
| 2 | Wait for first MariaDB service port liveness | `Bootstrap MariaDB cluster` | `wait_for` 3306 `search_regex MariaDB`, retries 10, delay 6 | `:23-34` |
| 3 | Wait for first MariaDB service to sync WSREP | `Bootstrap MariaDB cluster` | **changed in 2025.1:** `kolla_toolbox mysql_query` as `database_user` to the host's own address, until `Synced`, 10 x 6 s, with no `no_log` | `:36-52` |
| 4 | Ensure MariaDB is running normally on bootstrap host | `Bootstrap MariaDB cluster` | `group_by mariadb_bootstrap_restart` | `:54-57` |
| 5 | **Restart MariaDB on existing cluster members** | `Restart mariadb container` | `group_by mariadb_restart` for hosts in `<shard>_port_alive_True` | `:59-65` |
| 6 | Start MariaDB on new nodes | `Restart mariadb container` | `group_by mariadb_start` for hosts in `<shard>_port_alive_False` that are not `bootstrap_host` | `:67-74` |
| 7 | Restart mariadb-clustercheck container | (name) | `recreate_or_restart_container` on all notified hosts **at once**, only when the service is enabled and mapped | `:76-90` |

**Changed in 2025.1:** handlers 5 and 6 listen to `Restart mariadb container`, the name `service-check-containers`
builds from the key `mariadb` (`roles/service-check-containers/tasks/main.yml:41`), and no handler has the
`kolla_action != "config"` guard any more.

The monitor user is created by `register.yml` in post-configuration (`roles/mariadb/tasks/register.yml:19-34`) and by the loadbalancer
play (`roles/mariadb/tasks/loadbalancer.yml:18-40`).

`restart_services.yml` (run by the three restart plays of `mariadb.yml`): `recreate_or_restart_container mariadb` ->
wait for port 3306 (`timeout 60`, `retries 10`, `delay 6`) -> wait, through `kolla_toolbox mysql_query`, for WSREP
`Synced` (**10 x 6 s = about 60 s budget**). The WSREP wait is skipped for new nodes joining an existing cluster ("we
don't want to wait for new nodes to fully sync") (`roles/mariadb/tasks/restart_services.yml:1-53`).

**Rolling semantics (FACT, from the plays and the Ansible source):** the role play only fills the groups.
`Restart mariadb services` then runs `restart_services.yml` on the hosts of `mariadb_restart` in batches of
`serial: "33%"`, and `Start mariadb services` does the same for `mariadb_start` (`mariadb.yml:18-52`). The batch size is
`int(0.33 × N)`, at least 1 (section 0): with up to 6 hosts to restart, **one node at a time**, each waiting for port +
Synced before the next batch starts; with 7 to 9 hosts, 2 at a time; with 10 to 12, 3 at a time. That stays below a
third of the nodes, so a majority stays up while one batch restarts. NOT AVAILABLE: the order of the batches, which
follows the order in which `group_by` added the hosts to `mariadb_restart` (ansible-core 2.18.20
`lib/ansible/plugins/strategy/__init__.py:684-686`; `lib/ansible/executor/playbook_executor.py:276`), and so in which
batch node 0 restarts.
- **Failure mode:** if one node fails its port or 60 s WSREP-sync wait (for example a long IST/SST), only *that host* is
  marked failed. When that is every host of the batch (always so with up to 6 nodes, one host per batch), ansible-core
  stops the playbook and the later batches are not restarted; when other hosts of the batch succeed, the next batch
  still restarts its nodes (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:198-204`). The restart plays
  set `max_fail_percentage`, default 100, which adds no stop; an operator value (`mariadb_max_fail_percentage` or
  `kolla_max_fail_percentage`) lower than the failed share of a batch stops the play at that batch
  (`mariadb.yml:25-28,43-46`; ansible-core 2.18.20 `lib/ansible/plugins/strategy/linear.py:335-349`). They set no
  `any_errors_fatal`. NOT AVAILABLE: whether the failed node is then still joining, whether that can leave a single
  Synced node acting as donor, and so how large the quorum and availability risk is.

**Handler and play order consequences (FACT):**
- *First deploy:* `check-containers` notifies `Restart mariadb container` on every host (no container exists yet, so the
  compare reports a change), and the bootstrap host additionally gets `Bootstrap MariaDB cluster`. Order: handlers 1-3
  (bootstrap node up with `--wsrep-new-cluster` and Synced) -> 4 groups the bootstrap node -> 5 groups nothing (no alive
  nodes) -> 6 groups all other nodes -> 7. Then the `Start mariadb services` play starts the other nodes in 33 % batches,
  each waiting for Synced (the cluster did not exist), then `Restart bootstrap mariadb service` recreates the bootstrap
  node as a normal one (the `BOOTSTRAP` label differs), then post-configuration creates the users and runs `check.yml`.
  NOT AVAILABLE: what `compare_container` reports for a container that does not exist yet; the sequence above assumes it
  reports a change, as the first deploy needs.
- *Scale-out:* `Restart mariadb services` restarts the existing members first, batch by batch (their
  `wsrep_cluster_address` changed), then `Start mariadb services` starts the new nodes in batches without waiting for
  SST to finish.

### 1.6 Bootstrap, DB and registration; what re-runs on reconfigure

- `bootstrap_mariadb` runs **only** when no host had a `mariadb` volume and only on `groups[mariadb_shard_group][0]`
  (`bootstrap.yml:4-7`). It does not re-run on reconfigure.
- `register.yml` **runs on every deploy/reconfigure/upgrade** (post-configuration play), on the first host of the shard,
  logging in at that host's own `api_interface_address` (not the VIP): it creates the shard root user (`root` in HAProxy
  mode, `root_shard_<id>` with ProxySQL, password re-applied, `*.*:ALL,GRANT`) and the monitor user with
  `USAGE,REPLICATION CLIENT` (`roles/mariadb/tasks/register.yml:1-34`). When `enable_mariabackup` is set it also, on
  `mariadb_backup_host`, creates the backup user (`append_privs`, password re-applied) with
  `RELOAD,PROCESS,LOCK TABLES,BINLOG MONITOR` on `*.*` plus `CREATE,ALTER,INSERT` on `mysql.mariadb_backup_history`, and
  grants `CREATE,INSERT,SELECT` on `mysql.*` (`:36-72`). These tasks are unchanged from 2024.1 except the monitor
  privileges.
- `check.yml` runs on every deploy/reconfigure/upgrade, on every mariadb host, to the host itself (1.3).
- `lookup_cluster.yml` checks (port, WSREP, fail-fast) run on every deploy/reconfigure/upgrade/deploy-containers.
- Backup prerequisite: `my.cnf`, the backup user and the `mariabackup` config are created only by deploy/reconfigure
  with `enable_mariabackup: yes`. `kolla-ansible mariadb-backup` itself runs only `backup.yml`. A reconfigure is
  therefore required after enabling backups (`config.yml:12-57`, `register.yml:36-72`, `backup.yml:1-36`).

### 1.7 Dependencies

- **Explicit:** none in role metadata (no `meta/`). The loadbalancer play must have configured the database front end
  (HAProxy fragment, or ProxySQL users and rules), through `loadbalancer-config` (`roles/mariadb/tasks/loadbalancer.yml:42-47`;
  `roles/loadbalancer-config/tasks/main.yml:2-8`).
- **Implicit:**
  - **Changed in 2025.1:** the role's own checks no longer need the VIP: `lookup_cluster.yml`, `restart_services.yml`,
    `register.yml` and `check.yml` all log in at the node's own address (`lookup_cluster.yml:53`,
    `restart_services.yml:38`, `register.yml:8`, `check.yml:13`). The services still log in at `database_address`, the
    VIP (`group_vars/all.yml:89`).
  - `kolla_toolbox` (from `common`) for the `mysql_query` and `mysql_user` modules, which now carry the WSREP waits as
    well.
  - Facts: `hostname` (HAProxy server names, `wsrep_node_name`) and `memtotal_mb`.
- **Consumers:** the tasks of 29 roles use `kolla_toolbox mysql_db`
  (`grep -l "module_name: mysql_db" roles/*/tasks/*.yml`). The services log in at `database_address`, the VIP (for
  example `roles/keystone/defaults/main.yml:72`). Which backend receives writes now depends on ProxySQL's Galera host
  groups ([fact sheet A](a-infra-lb-ovn.md)); in HAProxy mode writes go to the first host of the default shard, every
  other server being `backup` (`roles/mariadb/defaults/main.yml:64`).

### 1.8 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a galera.cnf change.** The compare notifies every node, and the restart is batched by
   `Restart mariadb services` (`serial: "33%"`: 1 node at a time up to 6 nodes, `mariadb.yml:18-34`). Each batch waits
   for the port and `Synced` before the next. NOT AVAILABLE: how ProxySQL (the default) moves the writer away from a
   restarting node and back, and whether in-flight client connections are dropped at each step. In HAProxy mode the
   first host of the default shard is the only active backend, checked with `inter 2000 rise 2 fall 5`
   (`roles/mariadb/defaults/main.yml:64`).
2. **Clustercheck restart is not rolling (HAProxy mode only).** Handler 7 restarts `mariadb_clustercheck` on all
   notified nodes at once, in the role play (`roles/mariadb/handlers/main.yml:76-90`). With ProxySQL, the 2025.1 default, the container
   does not exist (`roles/mariadb/defaults/main.yml:132`). NOT AVAILABLE: whether HAProxy marks every backend down when that restart
   outlasts the check settings.
3. **WSREP-sync wait is only about 60 s** (`restart_services.yml:31-53`, 10 x 6 s at `:45-46`; handlers `:36-52`). A
   restart that needs IST or SST longer than that fails the host, and see the failure-mode note in 1.5.
4. **Fail-fast guards.** Reconfigure aborts if the cluster is fully stopped (multi-node) or any alive node is not Synced
   (`lookup_cluster.yml:36-43,73-79`). `kolla-ansible stop` stops every node at once (`service-stop`), so **the next
   deploy/reconfigure fails** until `kolla-ansible mariadb-recovery` is run.
5. **Recovery takes the whole cluster down.** It stops all `mariadb` containers unconditionally
   (`recover_cluster.yml:19-25`), starts all non-bootstrap nodes at once (concurrent SST/IST load on the single
   bootstrap node, `:175-204`), and restarts the bootstrap node after the others have only opened their port
   (`:206-235`). NOT AVAILABLE: whether restarting the bootstrap/donor node aborts a joiner's SST from it that is still
   running. **New in 2025.1:** `migrate-container-engine` goes through the same path on every MariaDB node (1.3).
6. **No longer holds in 2025.1:** the recovery bug of 2024.1. "Restart slave/master MariaDB container(s)" now loop over
   `mariadb_services | select_services_enabled_and_mapped_to_host` (`recover_cluster.yml:186,217`), so recovery no
   longer tries to start a disabled `mariadb_clustercheck`.
7. **Recovery assumptions.** It relies on the engine's volume directory on the host (`recover_cluster.yml:47,106`;
   `group_vars/all.yml:167`), a fixed `/tmp/mariadb_tmp.log` on each host (`:45-62`) and a fixed temp file per shard on
   the controller (`roles/mariadb/defaults/main.yml:113`), and it deletes every shard's temp file first (`recover_cluster.yml:7-16`),
   so concurrent recoveries from one controller would collide.
8. **Upgrade.** `mysql_upgrade` (`upgrade_mariadb`) runs on **all nodes concurrently** and on every upgrade, even when
   the image is unchanged, in the post-configuration play after the batched restarts (`mariadb.yml:70-92`,
   `roles/mariadb/tasks/post-upgrade.yml:2-24`). NOT AVAILABLE: whether concurrent `mysql_upgrade` on Galera nodes conflicts.
   **New in 2025.1:** an upgrade with ProxySQL removes `mariadb_clustercheck` on every mariadb host at the start of the
   role play (`roles/mariadb/tasks/upgrade.yml:2-9`). NOT AVAILABLE: the order in which, on a 2024.1 cloud that used HAProxy for the
   database, the loadbalancer play starts ProxySQL and the mariadb play removes the clustercheck, and whether
   connections are cut in between (to be confirmed by the community).
9. **Backup.** It runs only on `mariadb_backup_host`, the first host of the shard (`roles/mariadb/defaults/main.yml:123`;
   `backup.yml:34-36`), and `my.cnf` now points the client at that host's own address (`backup.my.cnf.j2:5-6`), so the
   tool reads the server whose files it copies. **Changed in 2025.1:** the image's `kolla_mariadb_backup.sh` writes
   `mysqlbackup-<date>.qp.xbc.xbs.gz` under `full-<date>/` (kolla `docker/mariadb/mariadb-server/backup.sh:7-21`). The
   image also ships `kolla_mariadb_backup_replica.sh`, which picks another Galera node from `wsrep_incoming_addresses`
   and backs it up (kolla `docker/mariadb/mariadb-server/Dockerfile.j2:41-42`, `backup_replica.sh:91-129`), but
   kolla-ansible 2025.1 always runs `kolla_mariadb_backup.sh` (`backup.yml:16`). Kolla-Ansible does not schedule or
   rotate backups (no such task in `roles/mariadb/tasks/`).
10. **Credentials.** **Changed in 2025.1:** most root logins now go through `kolla_toolbox`, which builds an
    `ansible localhost -m mysql_query -a "... login_password=..."` command and runs it inside `kolla_toolbox`
    (`library/kolla_toolbox.py:124-151`). The password therefore no longer appears in a `mysql -p` command on the host,
    but in the module arguments of a process in the `kolla_toolbox` container. `lookup_cluster.yml:46-59`,
    `restart_services.yml:31-47`, `check.yml:6-22` and handler 3 have no `no_log`. NOT AVAILABLE: what Ansible prints of
    those arguments at a given verbosity. `recover_cluster.yml:149` still runs `mariadb -uroot -p...` with `no_log`, and
    `galera.cnf` carries `wsrep_sst_auth` with the root password (`galera.cnf.j2:45`).
11. **Scale-out restarts the whole cluster**, batch by batch (`wsrep_cluster_address`, `galera.cnf.j2:33`).
12. **Oddity: hard-coded volume name.** The containers mount `mariadb_datadir_volume` (`roles/mariadb/defaults/main.yml:85`), but
    `lookup_cluster.yml` creates and tests the named volume `mariadb` (`lookup_cluster.yml:2-8`), and the backup
    container mounts `mariadb:/var/lib/mysql` (`backup.yml:31`). NOT AVAILABLE: what bootstrap detection and backup do
    when an operator sets `mariadb_datadir_volume` to another name or a host path.
13. **New oddity: `mariadb_backup_target` is never read.** `group_vars/all.yml:555` sets it to `replica` with ProxySQL,
    but no role, template or playbook of the 2025.1 tree uses it, and the replica backup script of the image is never
    called (item 9). NOT AVAILABLE: whether an operator setting it expects a replica backup that does not happen.
14. **New oddity: the "through VIP" check does not use the VIP** (`check.yml:6-14`). A deploy can therefore succeed
    while the database front end (ProxySQL or HAProxy) does not answer; the services find out later.

---

<a id="2-rabbitmq-ansiblerolesrabbitmq-used-twice"></a>

## 2. RabbitMQ (`ansible/roles/rabbitmq`)

**Still no longer holds:** "used twice". There is one broker cluster, and `rabbitmq.yml` has three plays
(`rabbitmq.yml:1-70`).

### 2.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial | Role vars |
|---|---|---|---|---|---|
| loadbalancer -> `include_role rabbitmq tasks_from: loadbalancer` | `site.yml:281-288` | loadbalancer | `rabbitmq` | loadbalancer play serial | `vars: role_rabbitmq_cluster_cookie: (null), role_rabbitmq_groups: (null)`, blanked so the lazily templated `rabbitmq_services` does not fail; `when: enable_rabbitmq` |
| `Apply role rabbitmq` | `rabbitmq.yml:3-28` | `rabbitmq` + `&enable_rabbitmq_True` | `rabbitmq` | **none** | `import_role` with `vars:` `role_rabbitmq_cluster_cookie: rabbitmq_cluster_cookie`, `_cluster_port: 25672`, `_epmd_port: 4369`, `_groups: rabbitmq`, `_management_port: 15672`, `_monitoring_user/_password`, `_password`, `_port: 5672` (5671 with TLS), `_prometheus_port: 15692`, `_user` (`rabbitmq.yml:17-28`; `group_vars/all.yml:706-710`) |
| `Restart rabbitmq services` | `rabbitmq.yml:30-49` | `rabbitmq_restart` + `&enable_rabbitmq_True` | `rabbitmq` | **`"33%"`** | runs `restart_services.yml` |
| `Apply rabbitmq post-configuration` | `rabbitmq.yml:51-70` | `rabbitmq` + `&enable_rabbitmq_True` | `rabbitmq` | none | `post-deploy.yml` (`rabbitmqctl enable_feature_flag all`) for deploy/reconfigure/upgrade |

- `enable_rabbitmq` defaults to yes when either `om_rpc_transport` or `om_notify_transport` is `rabbit`
  (`group_vars/all.yml:845`).
- `project_name` is `rabbitmq` (`roles/rabbitmq/vars/main.yml:2`), so the container, the config directory
  `/etc/kolla/rabbitmq`, the log dir and the restart group `rabbitmq_restart` all use that name
  (`roles/rabbitmq/defaults/main.yml:4,12,16`; `roles/rabbitmq/handlers/main.yml:4`).
- **What the absence of `kolla_serial` means:** `kolla_serial` is ignored. The role play handles every node in one
  batch; restarts come from the restart play with a fixed `serial: "33%"`.
- `--tags rabbitmq` (or `--skip-tags rabbitmq`) affects the broker plays and the loadbalancer fragment together.
- **Commands, changed in 2025.1:** there is no `kolla-ansible rabbitmq-upgrade` command any more (`setup.cfg:50-77`
  lists none). The playbook `rabbitmq-upgrade.yml` still exists and still builds the image name
  `rabbitmq-<rabbitmq_version_suffix with dots replaced by dashes>`, without `docker_image_name_prefix`
  (`rabbitmq-upgrade.yml:18-21`). The 2025.1 image repository has the default `rabbitmq` image with **RabbitMQ 4.0**
  (Erlang 26.2, kolla `docker/rabbitmq/rabbitmq/rabbitmq_packages_rpm.rocky:1-4`) and a `rabbitmq-4-1` image with
  RabbitMQ 4.1 (Erlang 27, kolla `docker/rabbitmq/rabbitmq-4-1/rabbitmq_packages_rpm.rocky:1-4`); the 2024.1 default
  was 3.13. `kolla-ansible rabbitmq-reset-state` runs `rabbitmqctl stop_app`, `force_reset`, `start_app` and
  `await_online_nodes` on **every** rabbitmq host, with no `serial` and no `max_fail_percentage`
  (`kolla_ansible/cli/commands.py:426-434`; `rabbitmq-reset-state.yml:1-9`; `roles/rabbitmq/tasks/reset-state.yml:1-16`).

### 2.2 `rabbitmq_services` (`ansible/roles/rabbitmq/defaults/main.yml:2-39`)

In 2025.1 the dict spans `roles/rabbitmq/defaults/main.yml:2-25`, as in 2024.1 (the heading keeps its earlier range so
that links stay stable).

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `rabbitmq` | `{{ project_name }}` (`rabbitmq`) | `{{ role_rabbitmq_groups }}` | `true` | `environment`: `KOLLA_CONFIG_STRATEGY`, **`RABBITMQ_CLUSTER_COOKIE: role_rabbitmq_cluster_cookie`**, `RABBITMQ_LOG_DIR`. `bootstrap_environment` adds `KOLLA_BOOTSTRAP` (`:8-16`). Data volume `{{ rabbitmq_datadir_volume }}:/var/lib/rabbitmq/` (`:52`), default `rabbitmq` (`group_vars/all.yml:1049`). Healthcheck `healthcheck_rabbitmq` when healthchecks are enabled (`:35-46`). HAProxy: only `rabbitmq_management` (http, 15672, `host_group: rabbitmq`) (`:20-25`). **AMQP 5672 is not load-balanced**: clients get every broker in `transport_url` |

Other defaults: `rabbitmq_pid_file: /var/lib/rabbitmq/mnesia/rabbitmq.pid` (`:59`),
`rabbitmq_server_additional_erl_args: "+S 2:2 +sbwt none ..."` (`:60`),
`rabbitmq_cluster_partition_handling: "pause_minority"` (`:64`), `rabbitmq_version_suffix: ""` (`:102`). The HA policy
settings are still defined (`:65-85`), but **no template reads them any more**: `definitions.json.j2` lost its policy
branch (2.4). **New in 2025.1:** `rabbitmq_copy_certs` (`kolla_copy_ca_into_containers` or TLS) and
`rabbitmq_enable_tls_backend` (`:104-108`).

**Erlang cookie:** comes from the `passwords.yml` key `rabbitmq_cluster_cookie` (`etc/kolla/passwords.yml:202`). It is
passed to the broker container as the env `RABBITMQ_CLUSTER_COOKIE` (`roles/rabbitmq/defaults/main.yml:11,15`). The `common` role also
writes it to `{{ node_config_directory }}/kolla-toolbox/rabbitmq-erlang.cookie` when `enable_rabbitmq` is set, and
`kolla_toolbox` copies it to `/var/lib/rabbitmq/.erlang.cookie` at every `COPY_ALWAYS` start
(`roles/common/tasks/config.yml:241-249`, `roles/common/templates/kolla-toolbox.json.j2:4-9`). That happens only when
the `common` play runs (an untagged run or `-t common`, `site.yml:88-103`). The kolla image writes
`/var/lib/rabbitmq/.erlang.cookie` **only** when `KOLLA_BOOTSTRAP` is set (kolla
`docker/rabbitmq/rabbitmq/extend_start.sh:7-26`; see
[Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)), that is
only in the `rabbitmq_bootstrap` container, which runs only when the volume was just created
(`roles/rabbitmq/tasks/bootstrap.yml:2-8,26`). The file persists in the data volume (`roles/rabbitmq/defaults/main.yml:52`). Because the cookie is in
the env, `compare_container` still picks up a cookie change and causes a **batched** recreate, but the recreated
brokers keep their old `.erlang.cookie` file. NOT AVAILABLE (it depends on whether `rabbitmq-server` itself reads
`RABBITMQ_CLUSTER_COOKIE`, which is not in these sources): whether a partition occurs during the roll, or whether the
change is silently not applied to existing brokers while `kolla_toolbox` and any broker bootstrapped later on a fresh
volume get the new cookie.

### 2.3 Task flow per `kolla_action`

| Action | Flow | Evidence |
|---|---|---|
| **deploy** | `version-check.yml` (`run_once`, delegated to the first rabbitmq host, tag `rabbitmq-version-check`; when a `rabbitmq` container is listed it fails if the new image's RabbitMQ is more than one minor version ahead of the running one, except 3.13 to 4.0 or 4.1, and on a downgrade) -> `remove-ha-all-policy.yml` (**now always**: clears an `ha-all` policy if one exists) -> `config.yml` -> `check-containers.yml` -> `bootstrap.yml`; handlers at the end of the role play; then the restart play and post-configuration (`enable_feature_flag all`) | `roles/rabbitmq/tasks/deploy.yml:1-10`, `version-check.yml:1-83` (`:45-65` minor-version gate, `:67-74` downgrade, `:76-80` scope), `remove-ha-all-policy.yml:1-30`; `rabbitmq.yml:30-70` |
| **reconfigure** | = deploy | `roles/rabbitmq/tasks/reconfigure.yml:2` |
| **bootstrap.yml** | `create_volume {{ project_name }}`. **Only when that volume was just created** on that host: run `rabbitmq_bootstrap` with `bootstrap_environment`, `detach: False` | `roles/rabbitmq/tasks/bootstrap.yml:1-26` |
| **upgrade** | `version-check.yml` -> `remove-ha-all-policy.yml` -> `config.yml` -> `feature-flags.yml` (on the running brokers, before their restart) -> `check-containers.yml`; then the restart play (drained, batched) and post-configuration. There is no bootstrap step and **no cluster-wide stop** | `roles/rabbitmq/tasks/upgrade.yml:1-10` |
| **deploy-containers** | `check-containers.yml` only. Handlers at the end of the role play, then the restart play | `roles/rabbitmq/tasks/deploy-containers.yml` |
| **pull** | `service-images-pull` | `roles/rabbitmq/tasks/pull.yml` |
| **stop** | `service-stop`: all nodes **at once** | `roles/rabbitmq/tasks/stop.yml` |
| **precheck** | group check, free ports, and `getent ahostsv4/6 <hostname>` for every rabbit host, failing unless every line resolves to that host's api IP (nodename `rabbit@<hostname>`); TLS files when TLS is on, now also accepting `kolla_tls_backend_cert`/`_key`. When a `rabbitmq` container exists: list the queues and assert that every queue except `reply_` and `_fanout` ones is a quorum queue, that `reply_` (and `_fanout` without stream fanout) queues are quorum, and that `_fanout` queues are streams while stream fanout is on. **Changed in 2025.1:** these asserts no longer depend on any switch, the `ha-all` policy assert is gone, and the `prechecks` role no longer compares HA and quorum ([F17](../findings.md#f17)) | `roles/rabbitmq/tasks/precheck.yml:1-164` (`:62-78`, `:80-108`, `:110-164`) |
| **check** | **New in 2025.1:** `check.yml` = `service-check` (container missing, not running or `unhealthy` fails), run by `kolla-ansible check` | `roles/rabbitmq/tasks/check.yml:2-4`; `kolla_ansible/cli/commands.py:495` |
| **config** | `config.yml`. Nothing notifies | `roles/rabbitmq/tasks/config.yml:1-106` |

### 2.4 Config files (`ansible/roles/rabbitmq/tasks/config.yml`)

All files go into `/etc/kolla/{{ project_name }}/`. Except `config.json`, each file uses **`with_first_found`**, which
means a **full replacement** of the template, not a merge:
`/etc/kolla/config/rabbitmq/<inventory_hostname>/<file>` -> `/etc/kolla/config/rabbitmq/<file>` -> the role template.
**Changed in 2025.1:** none of them notifies; the compare of `check-containers.yml` sees each one through `config.json`
and notifies `Restart rabbitmq container`.

| File | Template highlights | Lines |
|---|---|---|
| `config.json` | `rabbitmq.json.j2`: `/usr/sbin/rabbitmq-server`. Copies the config files, **new in 2025.1** the CA bundle to `/var/lib/kolla/share/ca-certificates` when `rabbitmq_copy_certs`, and on every `COPY_ALWAYS` start recursively chowns `/var/lib/rabbitmq` (the data volume, mnesia included) and `/var/log/kolla/{{ project_name }}` (`roles/rabbitmq/templates/rabbitmq.json.j2:2,51-57,59-70`) | `config.yml:12-18` |
| `rabbitmq-env.conf` | `RABBITMQ_NODENAME=rabbit@<hostname>`, `RABBITMQ_DIST_PORT=role_rabbitmq_cluster_port`, `RABBITMQ_PID_FILE`, `ERL_EPMD_ADDRESS=api ip`, `ERL_EPMD_PORT=role_rabbitmq_epmd_port` | `config.yml:20-32`; `roles/rabbitmq/templates/rabbitmq-env.conf.j2:1-10` |
| `rabbitmq.conf` | `listeners.tcp.1 = api_ip:role_rabbitmq_port` (`listeners.ssl.1` with TLS); **`cluster_partition_handling = pause_minority`**; management listener; `management.load_definitions = /etc/rabbitmq/definitions.json`; `cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config` with every host in `groups[role_rabbitmq_groups]` | `config.yml:34-46`; `roles/rabbitmq/templates/rabbitmq.conf.j2:3-21` |
| `erl_inetrc` | `{inet6,true}` for IPv6 | `config.yml:48-60` |
| `advanced.config` | `inet_dist_use_interface` and `inet_dist_listen_min/max = role_rabbitmq_cluster_port` | `config.yml:62-74`; `roles/rabbitmq/templates/advanced.config.j2:1-7` |
| `definitions.json` | vhost `/`; user `role_rabbitmq_user` (administrator) plus an optional monitoring user. **Changed in 2025.1: `"policies":[]` always**; the `ha-all` branch is gone | `config.yml:76-88`; `roles/rabbitmq/templates/definitions.json.j2:1-14` (policies `:13`) |
| `enabled_plugins` | `rabbitmq_management`, plus `rabbitmq_prometheus` when Prometheus is enabled | `config.yml:90-102`; `roles/rabbitmq/defaults/main.yml:91-98` |
| certificates | `copy-certs.yml` = `service-cert-copy` when `rabbitmq_copy_certs` (**changed in 2025.1**: also for the CA alone, without RabbitMQ TLS) | `config.yml:104-106`; `roles/rabbitmq/tasks/copy-certs.yml:2-6` |

**Oddity, still harmless:** the override paths are hard-coded to `/etc/kolla/config/rabbitmq/...` and do not include
`{{ project_name }}`; with a single broker they apply to `rabbitmq` (`config.yml:29-30`).

**`definitions.json` on the first 2025.1 run (FACT plus reasoning):** a 2024.1 cloud with the default
`om_enable_rabbitmq_high_availability: false` rendered `"policies":[]` from the `{% else %}` branch; the 2025.1 template
renders the same line without the `{% if %}` around it (`roles/rabbitmq/templates/definitions.json.j2:13`). NOT AVAILABLE: whether the
whitespace of the two renderings is identical, and so whether this file alone reports a change; on the first 2025.1 run
the unit drift of section 0 restarts the brokers anyway, batched.

### 2.5 Handlers (`ansible/roles/rabbitmq/handlers/main.yml`), in definition order

| # | Name | listen | Logic | Lines |
|---|---|---|---|---|
| 1 | Restart rabbitmq container | (name) | `group_by {{ project_name }}_restart`. **Changed in 2025.1:** no `kolla_action != "config"` guard | `:2-4` |

Still holds in 2025.1: there is no first-node-first rule.

`restart_services.yml` (run by the restart play): `kolla_container_facts get_containers rabbitmq` -> if that container
is listed: **with more than one rabbitmq host, put the node into maintenance mode** (`community.rabbitmq.rabbitmq_upgrade`
`action: drain`, through `kolla_toolbox`); **new in 2025.1, with a single host, `rabbitmqctl stop_app` instead** ->
`recreate_or_restart_container` (with env) -> `<engine> exec <c> rabbitmqctl wait --timeout 60
/var/lib/rabbitmq/mnesia/rabbitmq.pid`. There is **no cluster-membership, partition or quorum check**
(`roles/rabbitmq/tasks/restart_services.yml:1-49`). `get_containers` calls `client.containers.list()` without
`all=True` (`library/kolla_container_facts.py:136-150`). NOT AVAILABLE: whether the Docker and Podman clients then list
stopped containers, and so whether the drain step runs for a stopped broker.

**Rolling semantics (FACT, from the plays and the Ansible source):** `Restart rabbitmq services` runs
`restart_services.yml` on the hosts of `rabbitmq_restart` in `serial: "33%"` batches (`rabbitmq.yml:30-49`): **one node
at a time** with up to 6 notified nodes, 2 with 7 to 9 (section 0). Restart time grows linearly with N. Only notified
hosts are in the group. If every host of a batch fails (for example the `--timeout 60` wait), the playbook stops before
the next batch (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:198-204`). NOT AVAILABLE: the order of
the batches, which follows the order in which `group_by` added the hosts
(`lib/ansible/plugins/strategy/__init__.py:684-686`).

### 2.6 Bootstrap and registration

- The cluster/user bootstrap is declarative. Users, vhosts and policies come only from `definitions.json`, which is
  loaded at node boot (`rabbitmq.conf.j2:13`). There is no `rabbitmq_user` task in the role, so a **changed
  `rabbitmq_password` takes effect only through a restart** (batched, via the restart play). The role's `rabbitmqctl`
  calls are limited to the version check, the `ha-all` removal, feature flags, the single-node `stop_app`, the wait and
  `reset-state` (`version-check.yml:14`, `remove-ha-all-policy.yml:14,21`, `feature-flags.yml:3`,
  `restart_services.yml:24,49`, `reset-state.yml:1-16`); the precheck adds a read-only `list_queues` (`precheck.yml:113`).
- The `rabbitmq_bootstrap` container runs only on hosts whose volume is newly created (`bootstrap.yml:26`). It does not
  re-run on reconfigure.
- Per-service users and vhosts are created only by the `service-rabbitmq` role
  (`roles/service-rabbitmq/tasks/main.yml:1-45`), which in 2025.1 is still used only by `nova-cell`
  (`roles/nova-cell/tasks/rabbitmq.yml:5,15`). Every other service shares the `openstack` user on vhost `/`
  (`group_vars/all.yml:267-284`).

### 2.7 Dependencies

- **Explicit:** none in role metadata (no `meta/`).
- **Implicit:**
  - Hostnames must resolve to the api IP on every node (precheck), because nodenames are `rabbit@<hostname>`.
  - Facts (`hostname`).
  - `kolla_toolbox` (from `common`) for the drain step and `service-rabbitmq`.
  - HAProxy, only for the management UI.
- **Consumers:** the templates of 25 roles render `rpc_transport_url`, which lists **every** host in
  `groups['rabbitmq']` (`group_vars/all.yml:274,284`; `grep -l rpc_transport_url roles/*/templates`). Keystone is one of
  them (`keystone.conf.j2:4,54`). Every one of them now also renders `rabbit_quorum_queue`,
  `rabbit_transient_quorum_queue` and `use_queue_manager` unconditionally (for example `keystone.conf.j2:62-77`).

### 2.8 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a config change** drains and restarts the brokers in `serial: "33%"` batches, one node at a time
   with up to 6 nodes. At most one node is down at a time in that case, so a 3-node cluster keeps 2/3 and stays above
   the `pause_minority` threshold. The restart only runs `rabbitmqctl wait --timeout 60` and has no quorum check
   (`restart_services.yml:10-49`). NOT AVAILABLE: whether the next node may be stopped while the quorum queues of the
   freshly restarted node are still catching up.
2. **Upgrade = full outage of the message bus** still does not hold: `upgrade.yml` has no stop step
   (`roles/rabbitmq/tasks/upgrade.yml:1-10`); an image change goes through the same drained, batched restart play as a
   reconfigure (`rabbitmq.yml:30-49`). The version check refuses a downgrade and a jump of more than one minor version,
   except 3.13 to 4.0 or 4.1 (`version-check.yml:45-74`), so the 2024.1 default 3.13 may go to the 2025.1 default 4.0
   in one upgrade. **New oddity:** its failure message still tells the operator to run `kolla-ansible rabbitmq-upgrade`
   (`version-check.yml:64`), a command the 2025.1 CLI no longer has. The check runs only when a `rabbitmq` container is
   listed on the first rabbitmq host, and can be skipped with the tag `rabbitmq-version-check`
   (`version-check.yml:76-80`). NOT AVAILABLE: whether clients lose RPC while each node is drained and restarted, and
   what RabbitMQ 4.0 does with a cluster that still has classic mirrored queues (to be confirmed by the community).
3. **Uncontrolled full stop** (`kolla-ansible stop`, power loss) followed by deploy: the brokers come back through the
   batched restart play, one batch after another, each waiting `rabbitmqctl wait --timeout 60`. Which node starts first
   is NOT AVAILABLE (`group_by` order). NOT AVAILABLE (RabbitMQ semantics): whether a node that was not the last to stop
   waits for its peers' tables longer than 60 s. FACT: if it does, the wait fails, and with one node per batch (up to 6
   nodes) the playbook stops before the other nodes are started (section 0).
4. **Scaling the rabbitmq group changes `transport_url` in about 25 services**, so it restarts almost every OpenStack
   service cloud-wide when those plays run. It also changes `rabbitmq.conf` (classic_config node list,
   `rabbitmq.conf.j2:18-21`) on every broker, which causes a batched restart.
5. **Password change.** `definitions.json` changes cause a batched broker restart in the rabbitmq plays. Consumers get
   the new password only when their own plays run later in `site.yml`. NOT AVAILABLE: whether there is an auth-failure
   window in between.
6. **Single-node broker, new in 2025.1:** the restart stops the RabbitMQ application with `stop_app` before the
   container restart, instead of a drain (`restart_services.yml:22-27`).
7. The precheck runs `getent` for every rabbit host on every rabbit host, so it does N² lookups (`precheck.yml:62-78`).
8. **Quorum, transient quorum and stream fanout are always on ([F17](../findings.md#f17)).** A 2024.1 cloud with the
   2024.1 defaults had quorum queues but **not** transient quorum queues or stream fanout: `om_enable_queue_manager`
   was `false`, which turned both off (2024.1 `group_vars/all.yml:269-279`). On its first 2025.1 run every service
   renders `use_queue_manager = true`, `rabbit_transient_quorum_queue = true` and, by default, `rabbit_stream_fanout =
   true` (`keystone.conf.j2:62-77`; `group_vars/all.yml:292`), so its config changes and it restarts. The precheck then
   fails on that cloud's classic `reply_` queues and non-stream `_fanout` queues while they exist
   (`precheck.yml:131-158`). The release notes say the migration is manual (`releasenotes/notes/remove-om_enable_rabbitmq_high_availability-0e9ecae0240c516c.yaml`).
   NOT AVAILABLE: what oslo.messaging does with the existing classic transient queues and fanout exchanges when the
   services restart with these options (to be confirmed by the community).
9. **`ha-all` removal on every deploy.** `remove-ha-all-policy.yml` now runs unconditionally on deploy and upgrade
   (`deploy.yml:4`, `upgrade.yml:4`) and clears an `ha-all` policy from the first rabbitmq host when one exists
   (`remove-ha-all-policy.yml:18-24`). NOT AVAILABLE: what that does to a cloud that still relied on mirrored queues.
10. **Oddity: two volume names.** The broker mounts `rabbitmq_datadir_volume` (`roles/rabbitmq/defaults/main.yml:52`), but
    `bootstrap.yml` creates and tests the volume `{{ project_name }}` (`bootstrap.yml:2-8`). With the default both are
    `rabbitmq` (`group_vars/all.yml:1049`). NOT AVAILABLE: whether the cookie bootstrap runs for the real data volume
    when an operator sets another `rabbitmq_datadir_volume`.

---

## 3. Keystone (`ansible/roles/keystone`)

### 3.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial |
|---|---|---|---|---|
| loadbalancer -> `include_role keystone tasks_from: loadbalancer` | `site.yml:203-207` | loadbalancer | `keystone` | loadbalancer serial |
| `Apply role keystone` | `site.yml:498-510` | `keystone` + `&enable_keystone_True` | `keystone` | **`serial: '{{ kolla_serial\|default("0") }}'`** (`:503`) |

What serial means here:
- With `kolla_serial` unset or 0 (all hosts), every keystone node is handled in **one batch** (ansible-core 2.18.20
  `lib/ansible/executor/playbook_executor.py:295-297`), and handlers restart **all keystone containers at once**
  (section 0, "Handler order"). **Changed in 2025.1:** `reconfigure` and `upgrade` always pass `kolla_serial=0`, after
  the user's `-e`, so for these two actions the play cannot be batched ([F19](../findings.md#f19)). Only `deploy -e
  kolla_serial=N` (and the other actions that leave it unset) still batch.
- With a batch size n, `run_once` tasks run **once per batch**: bootstrap container (db_sync), key distribution,
  register. Each batch is a separate run on the inventory restricted to that batch, and `run_once` sends a task only to
  the first host left (`playbook_executor.py:183-188`, `lib/ansible/plugins/strategy/linear.py:197-206`).
- Fernet bootstrap is blocked when not all hosts are in the batch (3.6).
- On a batched run, `Init` (expand/migrate) runs in the batch containing `groups['keystone'][0]` and `Finish`
  (contract) in the batch containing `groups['keystone'][-1]`; since `upgrade` can no longer be batched, both now run
  in the single batch.

### 3.2 `keystone_services` (`ansible/roles/keystone/defaults/main.yml:2-55`)

In 2025.1 the dict spans `roles/keystone/defaults/main.yml:2-58` (the heading keeps its earlier range so that links stay
stable).

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `keystone` | `keystone` | `keystone` | `true` | Apache + mod_wsgi. Volumes include **`keystone_fernet_tokens:/etc/keystone/fernet-keys`** and, **now always**, `/dev/shm` (`:155-162`). HAProxy `keystone_internal` (`keystone_internal_port`, 5000) and `keystone_external` (`keystone_public_port`, 5000 unless the single external frontend is on) (`:11-31`; `group_vars/all.yml:508,510`). **New in 2025.1:** both backends add `option httpchk`, a layer-7 health check (`:21,32`). Healthcheck `healthcheck_curl` on port 5000 (`:116-127`) |
| `keystone-ssh` | `keystone_ssh` | `keystone` | `true` | `sshd -D` on `api_interface_address:8023` (`roles/keystone/templates/sshd_config.j2:1-2`, `group_vars/all.yml:513`). Shares the `keystone_fernet_tokens` volume (`:43`) |
| `keystone-fernet` | `keystone_fernet` | `keystone` | `true` | Runs cron with the rotation crontab. Healthcheck `fernet-healthcheck.sh` = `fernet-node-sync.sh --check && fernet-push.sh --check` (`:142-153`; `roles/keystone/templates/fernet-healthcheck.sh.j2:6`). Shares the `keystone_fernet_tokens` volume (`:56`) |

There is still no `keystone_token_provider`: `keystone.conf` sets `provider = fernet` unconditionally
(`roles/keystone/templates/keystone.conf.j2:32`), and the ssh and fernet containers are always enabled. **New in 2025.1:**
`keystone_copy_certs` (CA into containers or backend TLS) adds the CA bundle to all three `config.json` files, and
`keystone_database_enable_tls_internal` adds `?ssl_ca=` to the database URL (`roles/keystone/defaults/main.yml:250-256`;
`roles/keystone/templates/keystone.conf.j2:19`); `keystone_federation_oidc_forwarded_headers` and `_claim_delimiter` are new federation
options (`roles/keystone/defaults/main.yml:240-244`).

Relevant globals (`ansible/group_vars/all.yml`):

| Variable | Value | Line |
|---|---|---|
| `fernet_token_expiry` | 86400 | `:1113` |
| `fernet_token_allow_expired_window` | 172800 | `:1115` |
| `fernet_key_rotation_interval` | expiry + window = 259200 s (3 days) | `:1120` |
| `keystone_internal_url` | `keystone_internal_fqdn \| kolla_url(internal_protocol, keystone_internal_port)`, i.e. `<internal_protocol>://<internal VIP>:5000` | `:1093,1096` |
| `keystone_public_url` | `keystone_external_fqdn \| kolla_url(public_protocol, keystone_public_port)` | `:1097` |
| `openstack_auth.auth_url` | `keystone_internal_url` | `:1126-1132` |
| `multiple_regions_names` | `[openstack_region_name]` | `:809-810` |
| `keystone_default_user_role` | `member` | `:1122` |

### 3.3 Task flow per `kolla_action`

| Action | Flow | Evidence |
|---|---|---|
| **deploy** | `config.yml` -> `check-containers.yml` -> `clone.yml` (dev mode only) -> `bootstrap.yml` -> `flush_handlers` -> `distribute_fernet.yml` -> `register.yml` -> `register_identity_providers.yml` (federation only) | `roles/keystone/tasks/deploy.yml:1-21` |
| **reconfigure** | = deploy, so **bootstrap, distribution and registration all re-run** | `roles/keystone/tasks/reconfigure.yml:2` |
| **upgrade** | `config.yml` -> `check-containers.yml` -> set `log_bin_trust_function_creators=1` (`run_once`, on `groups['keystone'][0]`, as the shard root user, through `database_address`) -> notify `Init keystone database upgrade` on `[0]` -> notify `Finish keystone database upgrade` on `[-1]` -> `flush_handlers` -> set `log_bin_trust_function_creators=0` (`run_once`). **No** bootstrap or key distribution, no registration. Unchanged from 2024.1 | `roles/keystone/tasks/upgrade.yml:1-50`; `roles/keystone/defaults/main.yml:77` |
| **deploy-containers** | `check-containers.yml` | `roles/keystone/tasks/deploy-containers.yml` |
| **pull / stop** | `service-images-pull` / `service-stop` (all 3 containers, all hosts at once) | `roles/keystone/tasks/pull.yml`, `roles/keystone/tasks/stop.yml` |
| **precheck** | group check; free ports 5000 and 8023; **assert `fernet_token_expiry` is an int between 0 and 604800** | `roles/keystone/tasks/precheck.yml:1-61` |
| **check** | **New in 2025.1:** `check.yml` = `service-check` (any of the three containers missing, not running or `unhealthy` fails), run by `kolla-ansible check` | `roles/keystone/tasks/check.yml:2-4`; `kolla_ansible/cli/commands.py:495` |
| **config** | `config.yml`. Nothing notifies, and the handlers lost their `kolla_action != "config"` guard | `roles/keystone/handlers/main.yml:29-69` |

`bootstrap.yml` and `bootstrap_service.yml` (run on **every deploy/reconfigure**):
1. `mysql_db keystone` and `mysql_user keystone` with `keystone_database_password`, `append_privs` (`run_once`,
   `delegate_to: groups['keystone'][0]`, skipped with `use_preconfigured_databases`)
   (`roles/keystone/tasks/bootstrap.yml:1-36`). This re-asserts the DB user password on each run.
2. `kolla_container_facts get_containers keystone_fernet` -> **changed in 2025.1:**
   `group_by keystone_fernet_running_<True|False>`, from whether the container is **listed**, not from its `State`
   (`roles/keystone/tasks/bootstrap_service.yml:2-19`). `get_containers` lists with `containers.list()` and no
   `all=True` (`library/kolla_container_facts.py:136-150`). NOT AVAILABLE: whether the Docker and Podman clients list
   stopped containers there; the 2024.1 doubt about the Podman `State` value no longer applies.
3. Fail if no host has `keystone_fernet` running and not every keystone host is in `ansible_play_batch` ("Please run
   without --limit or --serial") (`:23-32`).
4. **`bootstrap_keystone` container** (`KOLLA_BOOTSTRAP`). In the kolla image, `kolla_start` sources
   `kolla_extend_start`, which sees `KOLLA_BOOTSTRAP`, runs `sudo -H -u keystone keystone-manage db_sync` and exits 0
   without starting httpd (kolla `docker/base/start.sh:21-24`, `docker/keystone/keystone/extend_start.sh:41-46`; see
   [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)).
   `EXTRA_KEYSTONE_MANAGE_ARGS` is empty by default (kolla `docker/keystone/keystone/extend_start.sh:21`) and
   kolla-ansible does not set it. It is `run_once` without `delegate_to` (first host of the batch) and runs **on every
   deploy/reconfigure** (`bootstrap_service.yml:34-51`).
5. `bootstrap_keystone_fernet`: `keystone-manage fernet_setup`, `run_once`, `delegate_to: groups['keystone'][0]`, **only
   if no `keystone_fernet` container is listed on any play host** (`:53-76`).

`distribute_fernet.yml` (every deploy/reconfigure):
- Wait for port 8023 on every host (`:2-10`).
- **`<engine> exec -t keystone_fernet /usr/bin/fernet-push.sh`**, `run_once`, `delegate_to` = the first host in
  `keystone_fernet_running_True`, or `groups['keystone'][0]` when that group does not exist (`:12-16`).

`register.yml` (every deploy/reconfigure):
- `<engine> exec keystone kolla_keystone_bootstrap <admin user> <admin pw> <project> admin <internal_url> <public_url> <region>`, once per region (`run_once`) (`roles/keystone/tasks/register.yml:2-12`).
- `service-ks-register` for the identity service and its endpoints (internal, public) (`:14-19`;
  `roles/keystone/defaults/main.yml:202-210`). **Changed in 2025.1:** `service-ks-register` uses the `openstack.cloud` modules
  (`catalog_service`, `endpoint`, `project`, `identity_user`, `identity_role`, `role_assignment`) with configurable
  retries (`roles/service-ks-register/tasks/main.yml:6,28,53,70,92,108`).
- `openstack.cloud.identity_role` `keystone_default_user_role` (`member`) (`:21-32`), formerly `os_keystone_role`.

### 3.4 Config files (`ansible/roles/keystone/tasks/config.yml`)

**Changed in 2025.1:** no task notifies. The compare of `check-containers.yml` sees each file listed in the service's
`config.json` and notifies `Restart <svc> container` (section 0).

| Destination (`/etc/kolla/...`) | Source / merge order | Seen by the compare of | Lines |
|---|---|---|---|
| `<svc>/config.json` | `keystone.json.j2` / `keystone-ssh.json.j2` / `keystone-fernet.json.j2` | the same service (command and entries) | `:42-48` |
| `keystone/keystone.conf`, `keystone-fernet/keystone.conf` | `merge_configs`: `roles/keystone/templates/keystone.conf.j2` + `/etc/kolla/config/global.conf` + `/etc/kolla/config/keystone.conf` + `/etc/kolla/config/keystone/<svc>.conf` + `/etc/kolla/config/keystone/<host>/keystone.conf` | `keystone` / `keystone-fernet` | `:50-65` |
| `keystone/keystone-startup.sh` | template. Waits up to 36 x 5 s (**3 min**) for fernet key `0`, then `exec httpd/apache2` | `keystone` | `:67-75`; `roles/keystone/templates/keystone-startup.sh.j2:9-24` |
| `keystone/domains/*` | Created only if `/etc/kolla/config/keystone/domains` exists on the controller. Every file in it is **templated** (Jinja) into `/etc/kolla/keystone/domains/`. `keystone.conf` gains `[identity] domain_specific_drivers_enabled = true, domain_config_dir = /etc/keystone/domains`. **Changed in 2025.1:** a file added once `keystone.conf` already has the domain settings is now seen as a change: `kolla_set_configs --check` finds the source file without its destination and exits 1 (kolla `docker/base/set_configs.py:178-182,233-255`), which the module reads as "changed" (`module_utils/kolla_docker_worker.py:169-172`), so `keystone` restarts instead of the 2024.1 failure of "Check keystone containers" | `keystone` | `:31-40,77-110`; `keystone.conf.j2:24-28`; `roles/keystone/templates/keystone.json.j2:25-31` |
| `<keystone, keystone-fernet>/<policy file>` | First found in `/etc/kolla/config/keystone/` (`supported_policy_format_list`) | the same service | `:12-29,112-125` |
| `keystone/wsgi-keystone.conf` | `with_first_found`: `/etc/kolla/config/keystone/<host>/wsgi-keystone.conf` -> `/etc/kolla/config/keystone/wsgi-keystone.conf` -> template. `processes = keystone_api_workers` = `openstack_service_workers` = min(vCPU, 5) (`roles/keystone/defaults/main.yml:173`, `group_vars/all.yml:812`) | `keystone` | `:127-139`; `roles/keystone/templates/wsgi-keystone.conf.j2:42` |
| `keystone/keystone-paste.ini` | Only if `/etc/kolla/config/keystone/keystone-paste.ini` exists | `keystone` | `:141-161` |
| (controller) cron generator | `python fernet_rotate_cron_generator.py -t <interval_s//60> -i <index in groups['keystone']> -n <len>`, `delegate_to: localhost`, per host | n/a (`changed_when: false`) | `:163-178` |
| `keystone-fernet/{crontab, fernet-rotate.sh, fernet-node-sync.sh, fernet-push.sh, fernet-healthcheck.sh, id_rsa, ssh_config}` | templates (`id_rsa` = `{{ keystone_ssh_key.private_key }}`) | `keystone-fernet` | `:180-197` |
| `keystone-ssh/{sshd_config, id_rsa.pub}` | templates (`id_rsa.pub` becomes `authorized_keys`) | `keystone-ssh` | `:199-210` |

`keystone.conf.j2` highlights:
- `transport_url = rpc_transport_url` (`:4`).
- `[database] connection` via the VIP, `max_retries = -1`, plus `?ssl_ca=` with database TLS (`:18-22`).
- `[token] provider = fernet`, `expiration`, `allow_expired_window` (`:30-34`).
- `[fernet_tokens] max_active_keys = ceil((expiry + window) / rotation_interval) + 2`, which is **3** with the defaults
  (`:43-46`).
- `[cache] backend = oslo_cache.memcache_pool`, `memcache_servers` = every `groups['memcached']` host (`:48-51`).
- `[oslo_messaging_notifications]` uses `notify_transport_url` and driver `messagingv2` only when ceilometer or barbican
  topics are enabled, otherwise `noop` (`:53-60`; `roles/keystone/defaults/main.yml:187-196`).
- **Changed in 2025.1:** `[oslo_messaging_rabbit]` renders `use_queue_manager = true`, `rabbit_quorum_queue = true` and
  `rabbit_transient_quorum_queue = true` unconditionally, plus `rabbit_stream_fanout` and `rabbit_qos_prefetch_count`
  with stream fanout (default on); `amqp_durable_queues` and the `[oslo_concurrency] lock_path` section are gone
  (`:62-77`; `group_vars/all.yml:292`). Booleans are now written in lower case (`use_stderr = true`, `:8`).

### 3.5 Handlers (`ansible/roles/keystone/handlers/main.yml`). Order is load-bearing (comment `:2-3`)

| # | Name | Logic | Lines |
|---|---|---|---|
| 1 | Init keystone database upgrade | `init_upgrade_database` container, `KOLLA_UPGRADE`, `run_once`, only when `kolla_action == upgrade` and the host is `groups['keystone'][0]` | `:5-27` |
| 2 | Restart keystone-ssh container | `recreate_or_restart_container`. All notified hosts in the batch **in parallel** | `:29-41` |
| 3 | Restart keystone-fernet container | same | `:43-55` |
| 4 | Restart keystone container | same: **no rolling, no wait for port or health** | `:57-69` |
| 5 | Finish keystone database upgrade | `finish_upgrade_database`, `KOLLA_FINISH_UPGRADE`, `run_once`, `kolla_action == upgrade`. No host guard: it relies on being notified only on `groups['keystone'][-1]` (`upgrade.yml:28-31`) | `:71-92` |

**Changed in 2025.1:** handlers 2 to 4 are notified by `service-check-containers` under the names it builds from the
keys of `keystone_services` (`roles/service-check-containers/tasks/main.yml:41`), and lost their
`kolla_action != "config"` guard. Their definition order, and so the run order, is unchanged.

ansible-core 2.18.20 runs a `run_once` handler once and then clears it for every other host
(`lib/ansible/plugins/strategy/linear.py:197-206`).

### 3.6 Fernet key lifecycle (FACT unless marked)

The fernet templates and the cron generator are unchanged since 2024.1 (`diff` of `roles/keystone/templates/fernet-*.j2`,
`roles/keystone/templates/crontab.j2`, `roles/keystone/templates/ssh_config.j2` and `roles/keystone/files/fernet_rotate_cron_generator.py` between the two tags
is empty).

- **Storage:** a per-host volume `keystone_fernet_tokens`, shared by the `keystone`, `keystone_fernet` and
  `keystone_ssh` containers (`roles/keystone/defaults/main.yml:43,56,162`).
- **Initial setup:** `keystone-manage fernet_setup` on `groups['keystone'][0]` only when no `keystone_fernet` container
  is *listed* anywhere in the play (`bootstrap_service.yml:53-76`). The code comment admits the detection is imprecise:
  "This does not catch some cases ... Probably what we care about is the existence of Fernet key 0" (`:11-15`). NOT
  AVAILABLE (Keystone upstream behaviour): whether `fernet_setup` is a no-op when key `0` already exists. On a
  **rebuilt `groups['keystone'][0]`** (empty volume), with every `keystone_fernet` container stopped and not listed (for
  example after `kolla-ansible stop`), a deploy runs `fernet_setup` on that node and then **pushes its key set with
  `rsync --delete` to every node** (`:53-76`; `distribute_fernet.yml:12-16`; `roles/keystone/templates/fernet-push.sh.j2:17-22`). NOT
  AVAILABLE: whether `fernet_setup` then generates brand-new keys and whether that invalidates all tokens; the code
  comment at `bootstrap_service.yml:21-22` names this risk.
- **Rotation:** cron in `keystone_fernet` runs `fernet-rotate.sh` = `keystone-manage fernet_rotate` && `fernet-push.sh`
  (`roles/keystone/templates/fernet-rotate.sh.j2:6-8`). `fernet-push.sh` runs, for each other keystone host,
  `rsync -az ... --delete /etc/keystone/fernet-keys/ keystone@<host>:/etc/keystone/fernet-keys` over ssh port 8023,
  under `set -o errexit` (`roles/keystone/templates/fernet-push.sh.j2:3,17-22`). With `--check` it does the same as a dry run, which
  the container healthcheck uses (`:6-15`).
- **Schedule:** the generator gives each host a weekly crontab (min hour * * dow) in round-robin with offset
  `interval * index` (`roles/keystone/files/fernet_rotate_cron_generator.py:39-94`; `roles/keystone/templates/crontab.j2:5-7`). It deliberately
  under-rotates across the week boundary (`:53-54,67`). Working through `generate()` for these inputs, which all take
  the day branch (offset `interval * index`, step `interval * hosts`, a job only while `time + interval <= 10080`;
  `:55-56,65-73`), gives:

  | Interval | Hosts | Result |
  |---|---|---|
  | 4320 min (default 3 days) | 3 | h0 = `Sun 00:00`, h1 = `Wed 00:00`, **h2 = no jobs**. Gaps 3 d / 4 d |
  | 4320 min | 5 | only h0 and h1 have jobs |
  | 1440 min | 3 | h0 Sun/Wed/Sat, h1 Mon/Thu, h2 Tue/Fri |

  Crons run in the container's local time (`/etc/localtime` is mounted, `roles/keystone/defaults/main.yml:53`).
- **Distribution on every deploy/reconfigure:** `fernet-push.sh` runs from the first running node
  (`distribute_fernet.yml:12-16`), so that node's key set **overwrites** every other node (`--delete`).

### 3.7 Bootstrap, DB and registration: what re-runs on `reconfigure`

Re-runs every time:
- `mysql_db` and `mysql_user keystone`
- the `bootstrap_keystone` container (db_sync)
- the fernet-bootstrap check
- `fernet-push.sh`
- `kolla_keystone_bootstrap` for each region. The keystone image installs kolla
  `docker/keystone/keystone/keystone_bootstrap.sh` under that name (kolla `docker/keystone/keystone/Dockerfile.j2:35`).
  Called with seven arguments it runs in its "no ADMIN_URL modern mode" (`keystone_bootstrap.sh:19-30`) and runs
  `keystone-manage bootstrap` with the admin user, password, project, role, internal/public URLs, service name
  `keystone` and the region (`:46`). It counts eight 'already exists'/'exists'/'already has'/'skipping' patterns but
  reports unchanged only when the count is nine (`:51-63`). NOT AVAILABLE (upstream `keystone-manage bootstrap` is not
  in these sources): whether the task can ever report unchanged, and whether `keystone-manage bootstrap` **resets the
  admin password to `keystone_admin_password`** if it differs.
- `service-ks-register` (identity service and endpoints)
- the `member` role

All of these are `run_once` per batch, except the cron generator, which runs on the controller once per host.

### 3.8 Dependencies

- **Explicit:** none in role metadata (no `meta/`).
- **Implicit, upstream:**
  - **MariaDB** via the VIP (`keystone_database_address`, `roles/keystone/defaults/main.yml:72`), ProxySQL by default.
  - **memcached**: `[cache]` (`keystone.conf.j2:48-51`). The memcached play (`site.yml:417`) runs before keystone
    (`:498`).
  - **RabbitMQ**: `transport_url` is always rendered, and notifications go out only if ceilometer or barbican is enabled
    (`keystone.conf.j2:4,53-60`).
  - **HAProxy VIP**: `keystone_internal_url` is used by `openstack_auth` for registration
    (`group_vars/all.yml:1126-1132`).
  - **kolla_toolbox** (`openstack.cloud` modules).
  - `passwords.yml` `keystone_ssh_key` (`etc/kolla/passwords.yml:170`).
- **Downstream:** see 3.10.

### 3.9 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a config change** restarts `keystone_ssh`, then `keystone_fernet`, then `keystone`, each **on all
   keystone hosts simultaneously** (handlers `:29-69`), only for the containers the compare reported changed. The
   result is a brief **Keystone-wide API outage** when `keystone` itself changed. Nothing waits for the API to return
   before `register.yml` runs (which uses `run_once` plus `until`/retries inside `service-ks-register`,
   `roles/service-ks-register/tasks/main.yml:20-22`). The containers have a healthcheck (`roles/keystone/defaults/main.yml:116-127`),
   and HAProxy now checks the backends over HTTP (`:21,32`), but the handlers do not wait for either. NOT AVAILABLE:
   whether other services keep validating cached tokens via memcached during the restart. **Changed in 2025.1:** a
   rolling `reconfigure` is no longer possible, since `kolla_serial` is forced to 0 ([F19](../findings.md#f19)); only a
   `deploy -e kolla_serial=N -t keystone` still restarts batch by batch. On the first 2025.1 run the same all-at-once
   restart follows from the unit-template drift ([F16](../findings.md#f16)) and from the changed `keystone.conf`
   (`keystone.conf.j2:62-77`), unless the upgrade already recreated the containers.
2. **What restarts keystone indirectly.** `keystone.conf` embeds every memcached host and every rabbitmq host
   (`keystone.conf.j2:4,51,54`), and the fernet crontab and `fernet-push.sh` embed the keystone host list and index.
   Adding or removing a memcached, rabbitmq or keystone node therefore restarts keystone, and keystone-fernet as well
   for keystone node changes.
3. **Fernet push has no partial-failure handling.** `set -o errexit` stops at the first unreachable peer, so later peers
   are not updated either (`fernet-push.sh.j2:3,17-22`). The next scheduled rotation runs on another node (round-robin,
   3.6), which may be one of the peers left with the *stale* set. That node runs `fernet_rotate` and then
   `fernet-push.sh`, whose `rsync --delete` overwrites the key set of each peer it reaches, stopping at the first
   failure (`roles/keystone/templates/fernet-rotate.sh.j2:6-8`, `roles/keystone/templates/fernet-push.sh.j2:3,17-22`). The reconfigure-time push from
   "first running node" works the same way. The `keystone_fernet` healthcheck (`fernet-push.sh --check`) reports such a
   failure as unhealthy (`roles/keystone/templates/fernet-healthcheck.sh.j2:6`), which `kolla-ansible check` now turns into a failure
   (3.3). NOT AVAILABLE (Keystone key handling): whether this removes the key that signed live tokens and so causes
   mass 401s.
4. **Bug in the cron generator hour calculation (still present).** In the day branch, `hour = time % HOUR_SPAN` is
   computed where `(time % DAY_SPAN) // HOUR_SPAN` was intended (`fernet_rotate_cron_generator.py:68-70`). It is
   harmless when the interval is a whole number of days (the default). Otherwise it can **over-rotate**: with interval
   3600 min (60 h), h1 gets `day 2 00:00` instead of `day 2 12:00` after h0's `day 0 00:00`, a **48 h gap with a 60 h
   interval**. NOT AVAILABLE (Keystone key handling): whether, with `max_active_keys=3`, a key can then be deleted
   before the allow-expired window of tokens it signed has elapsed.
5. **The precheck validates the wrong variable (still present).** It asserts `fernet_token_expiry <= 604800`
   (`precheck.yml:44-61`). The generator, however, is fed `fernet_key_rotation_interval` (= expiry + 2 d by default,
   `config.yml:163-168`) and fails above 10080 min (`fernet_rotate_cron_generator.py:59-62`). The generator exits 0 with
   `{"failed": true}` (`:31-36,116-117`), so the `command` task succeeds and **`set_fact cron_jobs` then errors on a
   missing key** outside check mode (`config.yml:175-178`). Any `fernet_token_expiry` above 5 days with the default
   window passes precheck but breaks deploy.
6. **Under-rotation by design.** With 3 or more hosts and the 3-day default, only 2 hosts ever rotate. Rotations happen
   at a fixed local `00:00` on Sunday and Wednesday.
7. **Shared SSH key.** Every node gets the same `keystone_ssh_key`, and `ssh_config` sets `StrictHostKeyChecking no`,
   `UserKnownHostsFile /dev/null` (`roles/keystone/templates/ssh_config.j2:1-4`). NOT AVAILABLE: whether anyone holding the private key
   and reaching port 8023 on the API network can overwrite fernet keys as `fernet-push.sh` does
   (`roles/keystone/templates/fernet-push.sh.j2:20`), and whether that allows token forgery.
8. **Domain config cleanup.** Removing a file from `/etc/kolla/config/keystone/domains` is never propagated: no task
   deletes stale files in `/etc/kolla/keystone/domains/`. Under `COPY_ALWAYS` the stale file is copied back into the
   container at every start: `domains` is a directory entry (`roles/keystone/templates/keystone.json.j2:25-31`), so
   `kolla_set_configs` deletes `/etc/keystone/domains` and re-copies the whole host directory (kolla
   `docker/base/set_configs.py:149-171,558-565`; see
   [Kolla images §2.3](../../concepts/kolla-images.md#23-kolla_set_configs-copy-and-permissions)). NOT AVAILABLE
   (Keystone semantics): whether Keystone keeps loading the stale file as a domain config. The task also re-uses the
   variable name `register: keystone_domains` (`config.yml:95,106`), which is an oddity.
9. **Upgrade.** All keystone APIs restart at once between `Init` (expand/migrate) and `Finish` (contract): `upgrade`
   can no longer be batched (section 0). The 2024.1 oddity of `log_bin_trust_function_creators` being reset at the end
   of every batch (`roles/keystone/tasks/upgrade.yml:36-50`) therefore no longer occurs through the CLI. NOT AVAILABLE: whether a cloud still
   has the admin endpoint that 2023.1 removed.
10. **Reconfigure re-asserts identity state.** It re-applies the admin credentials and endpoints, and the DB user
    password, from `passwords.yml` and globals. NOT AVAILABLE (`keystone-manage bootstrap` semantics): whether
    out-of-band changes are silently reverted.
11. **Oddity: queue-manager `processname` (still present, now always relevant).** `keystone.conf.j2` writes
    `processname` only when `service_name == 'keystone-api'` (`keystone.conf.j2:63-66`), but the template is rendered
    with `service_name` = `keystone` or `keystone-fernet` (`config.yml:52`), so that line is never written, while
    `use_queue_manager = true` is now always set (`:63`). NOT AVAILABLE: what oslo.messaging's queue manager does
    without it.

### 3.10 Runtime dependency of other services on Keystone (grep across `ansible/roles/*/templates`)

| Measure | Count | Pattern |
|---|---|---|
| Roles with `www_authenticate_uri` (keystonemiddleware `[keystone_authtoken]`) | **23** | **Changed in 2025.1:** `www_authenticate_uri = {{ keystone_public_url }}` (25 lines; 2024.1 used `keystone_internal_url`, for example 2024.1 `roles/nova/templates/nova.conf.j2:114`); 24 roles have a `[keystone_authtoken]` section |
| Roles with `auth_url` | **29** | `auth_url = {{ keystone_internal_url }}` (64 lines), `auth_url = {{ openstack_auth.auth_url }}` (1), `auth_url: {{ keystone_internal_url }}` (3), `auth_url: {{ keystone_public_url }}` (2) |
| Roles with `memcache_servers` / `memcached_servers` | **25** | (28 `memcached_servers =` lines + 6 `memcache_servers =`) |
| Roles with `memcache_secret_key` | **22** | Token cache in memcached with `memcache_security_strategy = {{ memcache_security_strategy }}`, default `ENCRYPT` (for example `roles/nova/templates/nova.conf.j2:112-126`; `group_vars/all.yml:576`) |
| Roles that call `service-ks-register` | **30** (keystone included) | During their deploy/reconfigure they create services, endpoints, users, roles and grants through `openstack_auth`, i.e. **`keystone_internal_url` on the internal VIP:5000** with `openstack_interface: internal`, `run_once`, with retries (`roles/service-ks-register/tasks/main.yml:1-129`, `roles/keystone/defaults/main.yml:1-40`; `group_vars/all.yml:823,1126-1132`) |

Every count is a recursive grep of the 2025.1 templates. Most are one lower than in 2024.1 (23, 30, 26, 23 and 31
roles), mainly because `roles/swift` was removed in 2025.1.

Implications:
- FACT: the `[keystone_authtoken]` sections of 24 roles point keystonemiddleware at Keystone, and 22 roles keep its
  token cache in memcached. NOT AVAILABLE: whether those API services fail to authenticate requests while Keystone or
  memcached is unavailable.
- Keystone, via the internal endpoint, is a **hard deploy-time dependency** for the `deploy`/`reconfigure` of 30 roles.
- Every service's `memcached_servers` and `transport_url` embed the full memcached and rabbitmq host lists, so changes
  to those groups fan out as restarts across the whole control plane.
- **New in 2025.1:** `www_authenticate_uri` now names the public Keystone URL in 25 places, so the first 2025.1 run
  changes the config of every service that has a `[keystone_authtoken]` section. NOT AVAILABLE: what clients see in the
  `WWW-Authenticate` header afterwards.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [findings F16, F17 and F19](../findings.md#f16)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
