---
title: Fact sheet B
description: "Fact sheet for MariaDB, RabbitMQ and Keystone: Galera bootstrap, recovery, backup and rolling restart, RabbitMQ, Keystone fernet keys."
tags: [mariadb, rabbitmq, keystone, mariadb-backup, mariadb-recovery, handlers]
---

# Fact sheet B

Source: `kolla-ansible` at tag `2023.1-eol` (commit `4891a21`), the kolla image repository at tag `2023.1-eol` and
ansible-core 2.14.18. Kolla-Ansible paths are relative to `ansible/` unless they start with `tools/` or `etc/`.
Labels: **FACT** = read directly from source code (cited): kolla-ansible, the kolla image repository (cited as kolla
`docker/...`) or Ansible (cited as ansible-core 2.14.18 `lib/ansible/...`). **NOT AVAILABLE** = these sources do not
establish it, often because it depends on upstream MariaDB, RabbitMQ, Keystone, HAProxy or Docker behaviour that is not
in them.

The supported Ansible range is ansible-core 2.13 to 2.14 (`roles/prechecks/vars/main.yml:4-5`,
`tools/kolla-ansible:10-11`). Statements about handler, serial and include semantics cite the ansible-core 2.14.18
source.

**What changed since Ussuri, in one paragraph (FACT):** MariaDB and RabbitMQ are no longer applied by a play of
`site.yml` but by their own playbooks, which `site.yml` imports (`site.yml:385,438`). In both, the role's handlers no
longer restart anything: they only put the hosts into `group_by` groups, and separate plays restart those groups in
`serial: "33%"` batches (`mariadb.yml:1-72`, `rabbitmq.yml:1-115`). RabbitMQ drains each node before its restart, and
`upgrade` no longer stops the whole cluster. MariaDB has shards and an optional ProxySQL load balancer, the xinetd
clustercheck and `wsrep-notify.sh` are gone, and `mysql_upgrade` runs in a post-configuration play. Keystone has no
admin endpoint any more, Fernet is the only token provider, and the sanity check is gone. No role has a `meta/main.yml`
dependency on `common` (sections below).

---

## 0. Shared context that applies to all three roles

| Topic | Fact | Evidence |
|---|---|---|
| Action dispatch | `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"`. mariadb first puts every `mariadb` host into its shard group (`mariadb_shard_<id>` via `add_host`, shard 0 by default); rabbitmq adds `when: inventory_hostname in groups[role_rabbitmq_groups]` | `roles/mariadb/tasks/main.yml:2-9`, `group_vars/all.yml:394-398`, `roles/keystone/tasks/main.yml:2`, `roles/rabbitmq/tasks/main.yml:2-3` |
| `common` dependency | None. The three roles have no `meta/` directory. `common` is its own play, tagged `common` (`site.yml:86-97`), so it runs only in an untagged run or with `-t common` | `ls roles/{mariadb,rabbitmq,keystone}` (no `meta`) |
| `common_run` guard | Gone: no `common_run` anywhere in `ansible/`. The `mariadb_recovery` and `mariadb_backup` commands run playbooks that contain only the mariadb role (`mariadb_recovery.yml:1-9`, `mariadb_backup.yml:1-7`), so `common` does not run. The CLI passes `kolla_action=deploy` for recovery and `kolla_action=backup -e mariadb_backup_type=...` for backup | `tools/kolla-ansible:437-446` |
| Serial | `kolla_serial` is passed only for `upgrade` and `reconfigure`, from `ANSIBLE_SERIAL` (default 0 = all hosts). The comment says "Serial is not recommended and disabled by default". The MariaDB and RabbitMQ restart plays ignore it: they use a fixed `serial: "33%"` | `tools/kolla-ansible:288-290,508,517`; `mariadb.yml:20,34`; `rabbitmq.yml:32,88` |
| Config strategy | `config_strategy: "COPY_ALWAYS"`, so `recreate_or_restart_container` restarts the container when its parameters are unchanged, and recreates it when they differ | `group_vars/all.yml:43`; `module_utils/kolla_docker_worker.py:362-384` |
| Graceful stop | Effective stop timeout is **60 s** (`docker_graceful_timeout`). `kolla_docker`'s `graceful_timeout` argument has no default in 2023.1, so the value from `docker_common_options` is used (`library/kolla_docker.py:303,351-382`; `group_vars/all.yml:140,152`). A container created with a restart policy other than `oneshot` gets a systemd unit whose `ExecStop` is `docker stop <name> -t <graceful_timeout>`, and stops go through that unit (`module_utils/kolla_docker_worker.py:356-360,436-452`; `module_utils/kolla_systemd_worker.py:33`). The Ussuri erratum (10 s) in [Per-role fact sheets](index.md) does not apply to 2023.1. Docker's own stop behaviour (which signal, when it kills) is NOT AVAILABLE from these sources. For MariaDB the image runs `dumb-init` without `--single-child` (kolla `docker/mariadb/mariadb-server/Dockerfile.j2:62-73`). The image's comment says that mysqld_safe ignores SIGTERM and that, without `--single-child`, TERM is sent to all subprocesses, including mysqld (kolla `Dockerfile.j2:64-68`). NOT AVAILABLE: the dumb-init and mysqld_safe behaviour itself, and so whether mysqld shuts down cleanly within the 60 s | `group_vars/all.yml:140,152`; `library/kolla_docker.py:303,360` |
| Bootstrap containers | `kolla_docker` defaults `remove_on_exit: True`, so `detach: False` bootstrap/upgrade containers are stopped and removed after they exit. They use `restart_policy: oneshot`, so they get no systemd unit. Containers started with a `BOOTSTRAP` label are later recreated because `compare_labels` sees a difference | `library/kolla_docker.py:304`; `module_utils/kolla_docker_worker.py:356-360,412-434`; `module_utils/kolla_container_worker.py:170-182` |
| `compare_environment` | Checks only that the *desired* env keys exist with equal values. Extra env vars on the running container (for example `BOOTSTRAP_ARGS`) are not detected; labels are what force the recreate | `module_utils/kolla_container_worker.py:307-318` |
| Handler order | Ansible runs handlers in the order they are **defined in `handlers/main.yml`**, not in notify order: at a flush each host walks the play's handler list and runs those it was notified for. Under the default `linear` strategy each handler is queued on every notified host before the results are awaited. This matters for the keystone handlers and for the order in which the mariadb `group_by` handlers fill their groups | ansible-core 2.14.18 `lib/ansible/executor/play_iterator.py:192-197,430-452`, `lib/ansible/plugins/strategy/linear.py:151,243,258` |
| Loadbalancer config | The loadbalancer play (`site.yml:99-341`; hosts `loadbalancer` + `&enable_loadbalancer_True`, `serial: kolla_serial`) runs `include_role ... tasks_from: loadbalancer` for each service, only when `enable_haproxy` and `kolla_action in ['deploy','reconfigure','upgrade','config']` | `site.yml:99-104,339-341` |
| Batch semantics of `serial: "33%"` | The batch size is `int(0.33 × N)`, at least 1, where N is the number of hosts the restart play targets: 1 host per batch up to 6 hosts, 2 for 7 to 9, 3 for 10 to 12. If every host of a batch fails, the playbook stops and later batches do not run; if only some fail, the next batch runs | ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:184-219,274-314`, `lib/ansible/utils/helpers.py:25-32` |

Play order in `site.yml` (relevant subset): loadbalancer `:99` -> **mariadb** (`import_playbook: mariadb.yml`, `:385`)
-> memcached `:387` -> **rabbitmq and outward rabbitmq** (`import_playbook: rabbitmq.yml`, `:438`) -> **keystone
`:450`** -> everything else (glance `:495` onward). Keystone therefore runs after its DB, cache and MQ dependencies, and
before every service that registers with Keystone.

---

## 1. MariaDB (`ansible/roles/mariadb`)

### 1.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial | Notes |
|---|---|---|---|---|---|
| `Apply role loadbalancer` -> `include_role mariadb tasks_from: loadbalancer` | `site.yml:213-217` | `loadbalancer` + `&enable_loadbalancer_True` (`:99-104`) | `mariadb` | loadbalancer play has `serial: kolla_serial` (`:104`) | `when: enable_mariadb or enable_external_mariadb_load_balancer`. Also ensures the monitor user (`haproxy`, or `monitor` with ProxySQL) on the first host of each shard, `run_once`, `failed_when: False` (`roles/mariadb/tasks/loadbalancer.yml:18-40`) |
| `Apply role mariadb` | `mariadb.yml:3-12` | `mariadb` + `&enable_mariadb_True` | `mariadb` | **none** | `gather_facts: false` (facts come from `gather-facts.yml`, `site.yml:2`) |
| `Restart mariadb services` | `mariadb.yml:14-26` | `mariadb_restart` + `&enable_mariadb_True` | `mariadb` | **`"33%"`** | runs `restart_services.yml` on the hosts that handler 5 grouped (1.5) |
| `Start mariadb services` | `mariadb.yml:28-40` | `mariadb_start` + `&enable_mariadb_True` | `mariadb` | **`"33%"`** | same task file, hosts grouped by handler 6 |
| `Restart bootstrap mariadb service` | `mariadb.yml:42-52` | `mariadb_bootstrap_restart` + `&enable_mariadb_True` | `mariadb` | none | the first-bootstrap host only (handler 4) |
| `Apply mariadb post-configuration` | `mariadb.yml:54-72` | `mariadb` + `&enable_mariadb_True` | `mariadb` | none | `post-deploy.yml` (`register.yml`, `check.yml`) for deploy/reconfigure/upgrade; `post-upgrade.yml` for upgrade |
| `Recover mariadb` | `mariadb_recovery.yml:1-9` | `mariadb` (no `enable_` intersection) | `mariadb` | none | play var `mariadb_recover: true`; role `when: enable_mariadb`. Uses implicit `gather_facts` (default on, ansible-core 2.14.18 `lib/ansible/executor/play_iterator.py:293-300`). CLI passes `kolla_action=deploy` (`tools/kolla-ansible:437-441`). The playbook has no restart plays |
| `Backup MariaDB` | `mariadb_backup.yml:1-7` | `mariadb` | `mariadb` | none | role `when: enable_mariabackup`. CLI passes `kolla_action=backup` and `mariadb_backup_type=full/incremental` (`tools/kolla-ansible:442-446`) |

**What the absence of `kolla_serial` means (FACT plus reasoning):**
- `ANSIBLE_SERIAL`/`kolla_serial` is **ignored** for MariaDB on `reconfigure` and `upgrade`. The role play handles all
  mariadb hosts in one batch, and the restart plays use their own `serial: "33%"`.
- This is required by the design. `lookup_cluster.yml` uses `group_by` and the `mariadb_shard_<id>_*` groups across the
  whole cluster in one pass (port liveness, WSREP state, volume existence) to decide bootstrap, fail-fast and which
  hosts are restarted or started (`roles/mariadb/tasks/lookup_cluster.yml:2-80`). Under serial these groups would only
  describe the current batch.
- Rolling behaviour comes from the **restart plays** (`serial: "33%"`, see 1.5), not from the handlers.
- `--limit` still narrows the plays: Ansible applies the limit when it resolves a play's hosts (ansible-core 2.14.18
  `lib/ansible/executor/playbook_executor.py:281`, `lib/ansible/inventory/manager.py:403-406`), and a `group_by` group
  only receives the hosts that ran the task (`lib/ansible/plugins/action/group_by.py:49`,
  `lib/ansible/plugins/strategy/__init__.py:667-669`). Group-derived decisions then only see the limited hosts (for
  example `mariadb_cluster_exists` is computed from `groups[mariadb_shard_group + '_had_volume_True']` among play
  hosts). The "existing but stopped" check uses the full shard length `groups[mariadb_shard_group] | length > 1`, filled
  by `add_host` from `groups['mariadb']` (`tasks/main.yml:2-7`, `lookup_cluster.yml:35-42`). FACT from these lines:
  `--limit` to a single new node on an existing cluster makes that node treat the cluster as new
  (`mariadb_cluster_exists=false`, `lookup_cluster.yml:10-17`), so in the `Start mariadb services` play it waits for
  WSREP Synced with only a 60 s budget (`restart_services.yml:31-51`).

### 1.2 `mariadb_services` (`ansible/roles/mariadb/defaults/main.yml:2-47`)

In 2023.1 the dict spans `roles/mariadb/defaults/main.yml:2-53` (the heading keeps its earlier range so that links stay
stable).

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `mariadb` | `mariadb` | `{{ mariadb_shard_group }}` (`mariadb_shard_0` by default) | `true` | Volumes: `/etc/kolla/mariadb`, named volume `mariadb:/var/lib/mysql` (`mariadb_datadir_volume`, `group_vars/all.yml:392`), `kolla_logs` (`:81-86`). Environment `MYSQL_USERNAME` (monitor user), `MYSQL_PASSWORD` (empty unless ProxySQL), `MYSQL_HOST`, `AVAILABLE_WHEN_DONOR=1` (`:11-15`). Container healthcheck `/usr/bin/clustercheck` when healthchecks are enabled (`:96-107`). HAProxy `mariadb` (internal, enabled unless external LB): `mode tcp`, client/server timeouts 3600 s, `option httpchk` when clustercheck is enabled, otherwise no check option (`:16-29`). `custom_member_list` = `internal_haproxy_members`, built from the hosts of the default shard, where **only the first host is active and every other host is `backup`**: `{% if not loop.first %} backup{% endif %}`, `check port 4569` (3306 without clustercheck) `inter 2000 rise 2 fall 5` (`:64`; `group_vars/all.yml:395`). HAProxy `mariadb_external_lb` uses inventory hostnames as addresses (`:30-41,65`). With `enable_proxysql` (default `no`, `group_vars/all.yml:742`) ProxySQL is the database load balancer instead (`mariadb_loadbalancer`, `group_vars/all.yml:399`); see [the loadbalancer page](../../components/haproxy-keepalived.md) |
| `mariadb-clustercheck` | `mariadb_clustercheck` | `{{ mariadb_shard_group }}` | `enable_mariadb_clustercheck` (defaults to `enable_haproxy`, `:132`) | Same environment as above (`:49-53`). `socat` on `mariadb_clustercheck_port` 4569 running `EXEC:clustercheck` (`templates/mariadb-clustercheck.json.j2:2`). The xinetd template of Ussuri is gone |

Other defaults: `database_max_timeout: 120` (`:59`); `mariadb_service: "{{ mariadb_services['mariadb'] }}"` is used by
the recovery and WSREP checks (`:112`); recovery temp file `/tmp/kolla_mariadb_recover_inventory_name_<shard>` (`:113`);
`mariadb_backup_host: "{{ groups[mariadb_shard_group][0] }}"` (`:123`); backup user `backup` (haproxy mode), schema
`PERCONA_SCHEMA` (`:124-125`). Ports: 3306, wsrep 4567, IST 4568, SST 4444, clustercheck 4569
(`group_vars/all.yml:385-389`). `enable_mariabackup: "no"` (`group_vars/all.yml:709`).

### 1.3 Task flow per `kolla_action`

| Action | Task files (in order) | Key behaviour |
|---|---|---|
| **deploy** | role play: `deploy.yml`: `config.yml` -> `check-containers.yml` -> `bootstrap.yml` (= `lookup_cluster.yml` -> `bootstrap_cluster.yml` [only if no cluster and host is `groups[mariadb_shard_group][0]`] -> `recover_cluster.yml` [only if `mariadb_recover`]); handlers at the end of the play. Then the restart, start and bootstrap-restart plays, then post-configuration: `register.yml` -> `check.yml` | `roles/mariadb/tasks/deploy.yml:1-6`, `bootstrap.yml:1-10`, `post-deploy.yml:1-4`; `mariadb.yml:3-66` |
| **reconfigure** | `import_tasks: deploy.yml` (identical to deploy) | `tasks/reconfigure.yml:2` |
| **upgrade** | role play: `upgrade.yml` = `deploy.yml`; restart plays; post-configuration: `post-deploy.yml`, then **"Run upgrade in MariaDB container"** (`upgrade_mariadb`, `KOLLA_UPGRADE`, `DB_HOST=api_interface_address`, `detach: False`) on **every** mariadb host, in a play without `serial`, with no `run_once` and no image-changed condition | `tasks/upgrade.yml:1-2`, `tasks/post-upgrade.yml:1-24`; `mariadb.yml:54-72` |
| **deploy-containers** | `check-containers.yml` -> `lookup_cluster.yml` (prerequisite for the handlers; comment `# handlers prerequisite`). Handlers at the end of the role play, then the restart plays. No post-configuration (`when` lists deploy/reconfigure/upgrade only) | `tasks/deploy-containers.yml:1-5`; `mariadb.yml:66` |
| **pull** | `service-images-pull` (pulls `mariadb` and `mariadb-clustercheck` if enabled) | `tasks/pull.yml`, `roles/service-images-pull/tasks/main.yml:1-18` |
| **stop** | `service-stop`: `stop_container` for each enabled, mapped service **on all hosts at once**, unless the name is in `skip_stop_containers` | `tasks/stop.yml`, `roles/service-stop/tasks/main.yml:1-12` |
| **precheck** | `service-precheck` (inventory group exists) plus free-port checks for 3306/4567/4568/4444, only if no `mariadb` container is running | `roles/mariadb/tasks/precheck.yml:1-55` |
| **check** | There is no `check` command in `tools/kolla-ansible` 2023.1. `check.yml` runs in post-configuration and at the end of recovery: from **every host of the default shard**, `docker exec mariadb mysql -h <VIP> -P 3306 -u <shard root user> -p<database_password> -e 'show databases;'`, 6 retries x 10 s | `roles/mariadb/tasks/check.yml:1-16`; `recover_cluster.yml:233` |
| **config** (genconfig) | `config.yml` (handlers guarded by `kolla_action != "config"`) | `handlers/main.yml:62,72,91` |
| **backup** | `backup.yml`: one-shot `mariabackup` container (`detach: False`, `remove_on_exit: True`) on `mariadb_backup_host` only (and only if `mariadb_backup_possible`), using the image of the running `mariadb` container when there is one, mounting `mariadb:/var/lib/mysql` and `mariadb_backup:/backup` and running `kolla_set_configs && /usr/local/bin/kolla_mariadb_backup.sh` with `BACKUP_TYPE` | `roles/mariadb/tasks/backup.yml:1-34`; `defaults/main.yml:127` |
| **recovery** (`mariadb_recovery`) | `kolla_action=deploy` with `mariadb_recover=true`, so `deploy.yml` runs and `bootstrap.yml` includes `recover_cluster.yml`. The port and WSREP block of `lookup_cluster.yml` is **skipped** (`when: not mariadb_recover`). `mariadb_recovery.yml` has no restart and no post-configuration plays, so `register.yml` does not run; `recover_cluster.yml` ends with `check.yml` | `lookup_cluster.yml:80`, `bootstrap.yml:9-10`, `recover_cluster.yml:233`; `mariadb_recovery.yml:1-9` |

#### `lookup_cluster.yml` (runs on deploy, reconfigure, upgrade and deploy-containers)

1. `create_volume mariadb`. If the volume already existed (not changed), the host joins group
   `mariadb_shard_<id>_had_volume_True` (`:2-13`).
2. `mariadb_cluster_exists = groups[mariadb_shard_group + '_had_volume_True'] is defined` (`:15-17`).
3. Unless recovering: `wait_for` port 3306 with `search_regex: MariaDB`, `timeout: 10`, `ignore_errors`, then
   `group_by mariadb_shard_<id>_port_alive_{True,False}` (`:19-33`).
4. **Fail fast** with "MariaDB cluster exists but is stopped. Please start it using kolla-ansible mariadb_recovery" if
   the shard has more than one node, the cluster exists and no node is alive (`:35-42`).
5. On alive nodes, `SHOW STATUS LIKE "wsrep_local_state_comment"`, then
   `group_by mariadb_shard_<id>_sync_status_<state>` (`:44-70`).
6. **Fail fast** with "MariaDB cluster is not synced" unless *every* alive node is `Synced` (`:72-78`). So a reconfigure
   refuses to run while any node is Donor or Joining.

#### First bootstrap (`bootstrap_cluster.yml`)

- On `groups[mariadb_shard_group][0]` only, when no host had a volume: run `bootstrap_mariadb` (`KOLLA_BOOTSTRAP`,
  `DB_ROOT_PASSWORD`, `DB_MAX_TIMEOUT`), `detach: False`, notify **`Bootstrap MariaDB cluster`**, and
  `set_fact bootstrap_host` (`roles/mariadb/tasks/bootstrap_cluster.yml:1-27`).

#### Recovery (`recover_cluster.yml`), in order

1. Fail if no cluster volume exists ("MariaDB cluster was not found. Is your inventory correct?") (`:2-5`).
2. Delete every `/tmp/kolla_mariadb_recover_inventory_name_*` file on the **controller** (`delegate_to: localhost`,
   `run_once`, `with_fileglob`) (`:7-16`).
3. The following block is skipped if `mariadb_recover_inventory_name` is supplied with `-e`, which lets the operator
   force the bootstrap host (`:94-95`):
   - **Stop the `mariadb` container on every host** (`:19-24`). This happens even if some nodes are healthy, so running
     recovery on a partially-up cluster causes a full DB outage.
   - Run `mariadb_wsrep_recovery` with `BOOTSTRAP_ARGS=--wsrep-recover`, `detach: false` (`:28-42`).
   - Copy `<docker_runtime_directory or /var/lib/docker>/volumes/kolla_logs/_data/mariadb/mariadb.log` to
     `/tmp/mariadb_tmp.log` on the host, then take the seqno of the last `Recovered position` line in the whole file
     with `awk` (`:44-53`), and delete the copy (`:55-61`). `seqno = stdout_lines[0]` (`:63-66`). NOT AVAILABLE: whether
     an empty parse makes that host fail and so drops it from the play.
   - Each host compares its seqno against every other host of its shard, using a bash regex guard. A host with **no
     larger peer** writes its own name to the controller temp file of its shard (`:68-88`). On a tie, every tied host
     writes and the last writer wins (harmless when the seqnos are equal).
   - Every host reads the chosen name with `lookup('file', ...)` (`:90-93`).
4. `bootstrap_host = mariadb_recover_inventory_name` (`:97-99`). On that host,
   `lineinfile grastate.dat safe_to_bootstrap: 1`, editing the Docker volume path on the host directly (`:101-111`).
5. On the bootstrap host: start a `mariadb` container with `BOOTSTRAP_ARGS: --wsrep-new-cluster`, label `BOOTSTRAP` and
   `restart_policy: oneshot` -> wait for the port -> `SET GLOBAL wsrep_provider_options='pc.bootstrap=yes'` -> wait for
   `wsrep_evs_state` to report `OPERATIONAL` (10 x 6 s) (`:113-169`).
6. **"Restart slave MariaDB container(s)"**: `start_container` loops over `with_dict: mariadb_services` on all other
   hosts **at once**, then waits only for the **port**, not for WSREP Synced (`:171-200`).
7. **"Restart master MariaDB container(s)"**: `recreate_or_restart_container` on the bootstrap host (drops the bootstrap
   args and label), then waits for the port (`:202-231`). Finally `check.yml` (`:233`).
8. Handlers notified earlier by config/check-containers do nothing for `restart mariadb`: they need the `_port_alive_*`
   groups, which recovery never creates (`handlers/main.yml:59-61,68-71`), and `mariadb_recovery.yml` has no restart
   plays anyway. Handler 7 (`restart mariadb-clustercheck`) still runs on the hosts it was notified on
   (`handlers/main.yml:75-91`).

### 1.4 Config files generated (`ansible/roles/mariadb/tasks/config.yml`)

| Destination (`/etc/kolla/...`) | Source / merge order | Notifies | Lines |
|---|---|---|---|
| `mariadb/`, `mariadb-clustercheck/` dirs | (directory), only for enabled services | none | `:2-13` |
| `mariabackup/` dir | only if `enable_mariabackup` and the host is `mariadb_backup_host` | none | `:15-25` |
| `mariabackup/my.cnf` | `merge_configs`: `templates/backup.my.cnf.j2` + `/etc/kolla/config/backup.my.cnf` + `/etc/kolla/config/mariadb/<host>/backup.my.cnf`. The template contains backup user/password and `host={{ database_address }}` (**VIP**) | **none** | `:27-40`; `templates/backup.my.cnf.j2:1-6` |
| `<svc>/config.json` (both services) | `templates/{mariadb,mariadb-clustercheck}.json.j2`. `mariadb.json.j2` recursively chowns `/var/log/kolla/mariadb` and `/var/lib/mysql` on every `COPY_ALWAYS` start, the bootstrap, upgrade and `--wsrep-recover` one-shots included (`templates/mariadb.json.j2:12-23`; [Kolla images §5.4](../../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)) | `restart <svc>` (`restart mariadb` / `restart mariadb-clustercheck`) | `:42-53` |
| `mariabackup/config.json` | `templates/mariabackup.json.j2` | none | `:55-65` |
| `mariadb/galera.cnf` | `merge_configs`: `templates/galera.cnf.j2` + `/etc/kolla/config/galera.cnf` + `/etc/kolla/config/mariadb/<host>/galera.cnf` | `restart mariadb` | `:67-83` |

`wsrep-notify.sh` and the clustercheck xinetd file are no longer generated: the role has no such templates in 2023.1
(`roles/mariadb/templates/`).

Notable `galera.cnf.j2` contents:
- `wsrep_cluster_address=gcomm://` lists **all** hosts of the shard group when there are two or more, and is empty on a
  single node (`:29`). Adding or removing a DB node therefore changes galera.cnf on every node of the shard, which
  triggers a batched restart of the whole shard.
- `innodb_buffer_pool_size` is 40 % of `ansible_facts.memtotal_mb`, capped at 8192M (`:50-55`). The file depends on
  facts, so a RAM change causes a restart.
- `wsrep_sst_method=mariabackup` and `wsrep_sst_auth={{ database_user }}:{{ database_password }}` (root credentials)
  (`:2,40-41`); `max_connections=10000` (`:45`). There is no `wsrep_notify_cmd` any more: the Ussuri mechanism that
  renamed the `haproxy` user while a node was not Synced is gone, and HAProxy's view of a node comes only from the
  clustercheck HTTP check (or a plain TCP check without clustercheck, `defaults/main.yml:28,64`).

### 1.5 Handlers (`ansible/roles/mariadb/handlers/main.yml`), in definition order

| # | Name | listen | Action / logic | Lines |
|---|---|---|---|---|
| 1 | Starting first MariaDB container | `Bootstrap MariaDB cluster` | `start_container mariadb` with `BOOTSTRAP_ARGS: --wsrep-new-cluster`, label `BOOTSTRAP`, `restart_policy: oneshot` | `:2-20` |
| 2 | Wait for first MariaDB service port liveness | `Bootstrap MariaDB cluster` | `wait_for` 3306 `search_regex MariaDB`, retries 10, delay 6 | `:23-34` |
| 3 | Wait for first MariaDB service to sync WSREP | `Bootstrap MariaDB cluster` | wait until `wsrep_local_state_comment == Synced`, 10 x 6 s | `:36-49` |
| 4 | Ensure MariaDB is running normally on bootstrap host | `Bootstrap MariaDB cluster` | `group_by mariadb_bootstrap_restart` | `:51-54` |
| 5 | **Restart MariaDB on existing cluster members** | `restart mariadb` | `group_by mariadb_restart` for hosts in `<shard>_port_alive_True`, unless `kolla_action == "config"` | `:56-63` |
| 6 | Start MariaDB on new nodes | `restart mariadb` | `group_by mariadb_start` for hosts in `<shard>_port_alive_False` that are not `bootstrap_host`, unless `config` | `:65-73` |
| 7 | Restart mariadb-clustercheck container | `restart mariadb-clustercheck` | `recreate_or_restart_container` on all notified hosts **at once**, unless `config` | `:75-91` |

The Ussuri handler "Creating haproxy mysql user" is gone: the monitor user is created by `register.yml` in
post-configuration (`tasks/register.yml:19-34`) and by the loadbalancer play (`tasks/loadbalancer.yml:18-40`).

`restart_services.yml` (run by the three restart plays of `mariadb.yml`): `recreate_or_restart_container mariadb` ->
wait for port 3306 (`timeout 60`, `retries 10`, `delay 6`) -> wait for WSREP `Synced` (**10 x 6 s = about 60 s
budget**). The WSREP wait is skipped for new nodes joining an existing cluster ("we don't want to wait for new nodes to
fully sync") (`roles/mariadb/tasks/restart_services.yml:1-51`).

**Rolling semantics (FACT, from the plays and the Ansible source):** the role play only fills the groups.
`Restart mariadb services` then runs `restart_services.yml` on the hosts of `mariadb_restart` in batches of
`serial: "33%"`, and `Start mariadb services` does the same for `mariadb_start` (`mariadb.yml:14-40`). The batch size is
`int(0.33 × N)`, at least 1 (section 0): with up to 6 hosts to restart, **one node at a time**, each waiting for port +
Synced before the next batch starts; with 7 to 9 hosts, 2 at a time; with 10 to 12, 3 at a time. That stays below a
third of the nodes, so a majority stays up while one batch restarts. NOT AVAILABLE: the order of the batches, which
follows the order in which `group_by` added the hosts to `mariadb_restart`
(`lib/ansible/plugins/strategy/__init__.py:667-669`; `lib/ansible/executor/playbook_executor.py:281`), and so in which
batch node 0, the active HAProxy backend, restarts.
- **Failure mode:** if one node fails its port or 60 s WSREP-sync wait (for example a long IST/SST), only *that host* is
  marked failed. When that is every host of the batch (always so with up to 6 nodes, one host per batch), ansible-core
  stops the playbook and the later batches are not restarted; when other hosts of the batch succeed, the next batch
  still restarts its nodes (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:204-208,218-219`). The
  restart plays set neither `any_errors_fatal` nor `max_fail_percentage` (`mariadb.yml:14-40`). NOT AVAILABLE: whether
  the failed node is then still joining, whether that can leave a single Synced node acting as donor, and so how large
  the quorum and availability risk is.

**Handler and play order consequences (FACT):**
- *First deploy:* config/check-containers notify `restart mariadb` on every host, and the bootstrap host additionally
  gets `Bootstrap MariaDB cluster`. Order: handlers 1-3 (bootstrap node up with `--wsrep-new-cluster` and Synced) -> 4
  groups the bootstrap node -> 5 groups nothing (no alive nodes) -> 6 groups all other nodes -> 7. Then the
  `Start mariadb services` play starts the other nodes in 33 % batches, each waiting for Synced (the cluster did not
  exist), then `Restart bootstrap mariadb service` recreates the bootstrap node as a normal one (the `BOOTSTRAP` label
  differs), then post-configuration creates the users and runs `check.yml`.
- *Scale-out:* `Restart mariadb services` restarts the existing members first, batch by batch (their
  `wsrep_cluster_address` changed), then `Start mariadb services` starts the new nodes in batches without waiting for
  SST to finish.

### 1.6 Bootstrap, DB and registration; what re-runs on reconfigure

- `bootstrap_mariadb` runs **only** when no host had a `mariadb` volume and only on `groups[mariadb_shard_group][0]`
  (`bootstrap.yml:4-7`). It does not re-run on reconfigure.
- `register.yml` **runs on every deploy/reconfigure/upgrade** (post-configuration play), on the first host of the shard,
  logging in at that host's own `api_interface_address` (not the VIP): it creates the shard root user (`root` in HAProxy
  mode, password re-applied, `*.*:ALL,GRANT`) and the monitor user. When `enable_mariabackup` is set it also, on
  `mariadb_backup_host`, creates `PERCONA_SCHEMA`, creates the backup user (`append_privs`, password re-applied) and
  grants on the schema (`roles/mariadb/tasks/register.yml:1-87`; `defaults/main.yml:137`). The Ussuri
  `wait_for_loadbalancer` step is gone.
- `check.yml` runs on every deploy/reconfigure/upgrade, from every default-shard host through the VIP, as the shard root
  user with `database_password` on the command line (`roles/mariadb/tasks/check.yml:1-16`).
- `lookup_cluster.yml` checks (port, WSREP, fail-fast) run on every deploy/reconfigure/upgrade/deploy-containers.
- Backup prerequisite: `my.cnf`, the backup user and the `mariabackup` config are created only by deploy/reconfigure
  with `enable_mariabackup: yes`. `kolla-ansible mariadb_backup` itself runs only `backup.yml`. A reconfigure is
  therefore required after enabling backups (`config.yml:15-65`, `register.yml:36-87`, `backup.yml`; the docs at
  `doc/source/admin/mariadb-backup-and-restore.rst` describe this step).

### 1.7 Dependencies

- **Explicit:** none in role metadata (no `meta/`). The loadbalancer play must have configured the `mariadb` frontend,
  which uses `loadbalancer-config` (`tasks/loadbalancer.yml:42-47`).
- **Implicit:**
  - The **VIP (haproxy + keepalived, or ProxySQL) must be up** for `check.yml`, which connects to `database_address` =
    `kolla_internal_fqdn` (`group_vars/all.yml:83`), so the post-configuration play fails without the load balancer.
    `register.yml` connects to the node directly.
  - `kolla_toolbox` (from `common`) for the `mysql_user`/`mysql_db` modules.
  - Facts: `hostname` (HAProxy server names, `wsrep_node_name`) and `memtotal_mb`.
- **Consumers:** the tasks of 36 roles use `kolla_toolbox mysql_db`, the mariadb role's own `PERCONA_SCHEMA` task
  included (`grep -l "module_name: mysql_db" roles/*/tasks/*.yml`); the services log in at `database_address`, the VIP
  (for example `roles/keystone/tasks/bootstrap.yml:8`). Writes go to a single active backend, the first host of the
  default shard, because every other server is `backup` in HAProxy (`defaults/main.yml:64`).

### 1.8 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a galera.cnf change.** Every node is notified, and the restart is batched by
   `Restart mariadb services` (`serial: "33%"`: 1 node at a time up to 6 nodes, `mariadb.yml:14-26`). Each batch waits
   for the port and `Synced` before the next. The first host of the default shard is the **only active HAProxy backend**
   and is restarted in one of the batches (which one is NOT AVAILABLE, see 1.5). HAProxy checks each server with
   `inter 2000 rise 2 fall 5` (`defaults/main.yml:64`). NOT AVAILABLE: how long HAProxy takes to fail over to a backup
   node and back, and whether in-flight client connections are dropped at each step.
2. **Clustercheck restart is not rolling.** Handler 7 restarts `mariadb_clustercheck` on all notified nodes at once, in
   the role play (`handlers/main.yml:75-91`). HAProxy health checks for every backend go through port 4569 when
   clustercheck is enabled (`defaults/main.yml:28,64`). NOT AVAILABLE: whether HAProxy marks every backend down when
   that restart outlasts the `fall 5` x `inter 2000` check settings, which would mean a short total DB outage through
   the VIP.
3. **WSREP-sync wait is only about 60 s** (`restart_services.yml:31-51`, 10 x 6 s at `:42-43`; handlers `:36-49`). A
   restart that needs IST or SST longer than that fails the host, and see the failure-mode note in 1.5.
4. **Fail-fast guards.** Reconfigure aborts if the cluster is fully stopped (multi-node) or any alive node is not Synced
   (`lookup_cluster.yml:35-42,72-78`). `kolla-ansible stop` stops every node at once (`service-stop`), so **the next
   deploy/reconfigure fails** until `mariadb_recovery` is run.
5. **Recovery takes the whole cluster down.** It stops all `mariadb` containers unconditionally
   (`recover_cluster.yml:19-24`), starts all non-bootstrap nodes at once (concurrent SST/IST load on the single
   bootstrap node, `:171-200`), and restarts the bootstrap node after the others have only opened their port
   (`:202-231`). NOT AVAILABLE: whether restarting the bootstrap/donor node aborts a joiner's SST from it that is still
   running.
6. **Recovery bug:** "Restart slave/master MariaDB container(s)" loop over `with_dict: mariadb_services` with no
   `item.value.enabled` or group check (`recover_cluster.yml:171-185,202-216`). With `enable_mariadb_clustercheck: no`,
   recovery still tries to start a `mariadb_clustercheck` container: `kolla_docker` pulls the image if it is not
   present, then creates and starts the container (`module_utils/kolla_docker_worker.py:386-407`). If the pull returns
   an error, `kolla_docker` fails the task on that host (`:217-230`). FACT. In deploy and reconfigure the clustercheck
   container is handled only when enabled (`config.yml:42-53`, `check-containers.yml:13-18`).
7. **Recovery assumptions.** It relies on `/var/lib/docker` volume paths on the host (`recover_cluster.yml:46,105`), a
   fixed `/tmp/mariadb_tmp.log` on each host (`:44-61`) and a fixed temp file per shard on the controller
   (`defaults/main.yml:113`), and it deletes every shard's temp file first (`recover_cluster.yml:7-16`), so concurrent
   recoveries from one controller would collide.
8. **Upgrade.** `mysql_upgrade` (`upgrade_mariadb`) runs on **all nodes concurrently** and on every upgrade, even when
   the image is unchanged, in the post-configuration play after the batched restarts (`mariadb.yml:54-72`,
   `tasks/post-upgrade.yml:2-24`). NOT AVAILABLE: whether concurrent `mysql_upgrade` on Galera nodes conflicts.
9. **Backup.** It runs only on the first host of the shard (reading that node's datadir, `defaults/main.yml:123`;
   `backup.yml:33-34`), but `my.cnf` points the client at `database_address`, the **VIP** (`backup.my.cnf.j2:5`). NOT
   AVAILABLE: whether, if HAProxy has failed over away from node 0, the backup tool connects to a different server than
   the one whose files it copies. Kolla does not schedule or rotate backups (docs).
10. **Credentials on the command line.** Root credentials appear in
    `docker exec ... mysql -uroot -p{{ database_password }}` command lines (`lookup_cluster.yml:47-51`,
    `restart_services.yml:33-38`, `recover_cluster.yml:148`, handlers `:38-42`) and in `check.yml`'s
    `-p{{ database_password }}` (`check.yml:7-10`). `no_log` hides the first ones from Ansible output but not from the
    host process list; `check.yml` has no `no_log` (`check.yml:5-16`).
11. **Scale-out restarts the whole cluster**, batch by batch (`wsrep_cluster_address`, `galera.cnf.j2:29`). Every time
    the loadbalancer play runs, `internal_haproxy_members` is also re-rendered in haproxy.

---

## 2. RabbitMQ (`ansible/roles/rabbitmq`), used twice

### 2.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial | Role vars |
|---|---|---|---|---|---|
| loadbalancer -> `include_role rabbitmq tasks_from: loadbalancer` | `site.yml:276-283` | loadbalancer | `rabbitmq` | loadbalancer play serial | `vars: role_rabbitmq_cluster_cookie: (null), role_rabbitmq_groups: (null)`. These are blanked so the lazily templated `rabbitmq_services` does not fail. `when: enable_rabbitmq or enable_outward_rabbitmq` |
| `Apply role rabbitmq` | `rabbitmq.yml:3-24` | `rabbitmq` + `&enable_rabbitmq_True` | `rabbitmq` | **none** | `import_role` with `vars:` `role_rabbitmq_cluster_cookie: rabbitmq_cluster_cookie`, `_cluster_port: 25672`, `_epmd_port: 4369`, `_groups: rabbitmq`, `_management_port: 15672`, `_monitoring_user/_password`, `_password`, `_port: 5672`, `_prometheus_port: 15692`, `_user` (`group_vars/all.yml:502-506`) |
| `Restart rabbitmq services` | `rabbitmq.yml:26-41` | `rabbitmq_restart` + `&enable_rabbitmq_True` | `rabbitmq` | **`"33%"`** | runs `restart_services.yml` |
| `Apply rabbitmq post-configuration` | `rabbitmq.yml:43-58` | `rabbitmq` | `rabbitmq` | none | `post-deploy.yml` (`rabbitmqctl enable_feature_flag all`) for deploy/reconfigure/upgrade |
| `Apply role rabbitmq (outward)` | `rabbitmq.yml:60-80` | `outward-rabbitmq` + `&enable_outward_rabbitmq_True` | `rabbitmq` (**same tag**) | **none** | **`project_name: outward_rabbitmq`**, `outward_rabbitmq_cluster_cookie`, ports 5674/15674/25674/4371/15694 (`group_vars/all.yml:460-464`), `_groups: outward-rabbitmq`, no monitoring user |
| `Restart rabbitmq (outward) services` | `rabbitmq.yml:82-98` | `outward_rabbitmq_restart` + `&enable_outward_rabbitmq_True` | `rabbitmq` | **`"33%"`** | `project_name: outward_rabbitmq` |
| `Apply rabbitmq (outward) post-configuration` | `rabbitmq.yml:100-115` | `outward-rabbitmq` | `rabbitmq` | none | includes the **whole role** (no `tasks_from`), for deploy/reconfigure ([RabbitMQ](../../components/rabbitmq.md)) |

- `enable_rabbitmq` defaults to yes when either `om_rpc_transport` or `om_notify_transport` is `rabbit`
  (`group_vars/all.yml:631`). `enable_outward_rabbitmq` = `enable_murano` (`:632`).
- **Play-level vars override role vars.** The `vars:` of an `import_role` reach the role's tasks as task vars, which
  Ansible merges after the role's `vars/main.yml` (`project_name: "rabbitmq"`) (ansible-core 2.14.18
  `lib/ansible/vars/manager.py:397-399`). For the outward cluster, `project_name=outward_rabbitmq` therefore drives the
  container name, the volume name, the config dir `/etc/kolla/outward_rabbitmq`, the log dir, the restart group
  `outward_rabbitmq_restart` and the murano-specific definitions (`roles/rabbitmq/defaults/main.yml:4,12,16,71,74`;
  `handlers/main.yml:4`; `templates/definitions.json.j2:3,9,15`).
- **What the absence of `kolla_serial` means:** `kolla_serial` is ignored. The role play handles every node in one
  batch; restarts come from the restart plays with a fixed `serial: "33%"`.
- `--tags rabbitmq` (or `--skip-tags rabbitmq`) affects **both** clusters and the loadbalancer fragment together.
- New commands in 2023.1: `kolla-ansible rabbitmq-upgrade <version>` imports `rabbitmq.yml` with `kolla_action: upgrade`
  and the image `rabbitmq-<version>` (`rabbitmq-upgrade.yml:18-21`; `tools/kolla-ansible:568-572`);
  `kolla-ansible rabbitmq-reset-state` runs `rabbitmqctl stop_app`, `force_reset`, `start_app` and `await_online_nodes`
  on **every** rabbitmq host, with no `serial` (`rabbitmq-reset-state.yml:1-9`;
  `roles/rabbitmq/tasks/reset-state.yml:1-16`).

### 2.2 `rabbitmq_services` (`ansible/roles/rabbitmq/defaults/main.yml:2-39`)

In 2023.1 the dict spans `roles/rabbitmq/defaults/main.yml:2-40` (the heading keeps its earlier range so that links stay
stable).

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `rabbitmq` | `{{ project_name }}` (`rabbitmq` or `outward_rabbitmq`) | `{{ role_rabbitmq_groups }}` | `true` | `environment`: `KOLLA_CONFIG_STRATEGY`, **`RABBITMQ_CLUSTER_COOKIE: role_rabbitmq_cluster_cookie`**, `RABBITMQ_LOG_DIR`. `bootstrap_environment` adds `KOLLA_BOOTSTRAP`. Volume `{{ project_name }}:/var/lib/rabbitmq/`. Healthcheck `healthcheck_rabbitmq` when healthchecks are enabled (`:57-68`). HAProxy: `rabbitmq_management` (http, 15672, `host_group: rabbitmq`), `rabbitmq_outward_management` (15674), and `rabbitmq_outward_external` (tcp, **external** frontend on 5674 for murano agents, 1 h timeouts). **AMQP 5672 is not load-balanced**: clients get every broker in `transport_url` |

Other defaults: `rabbitmq_pid_file: /var/lib/rabbitmq/mnesia/rabbitmq.pid` (`:81`),
`rabbitmq_server_additional_erl_args: "+S 2:2 +sbwt none ..."` (`:82`),
`rabbitmq_cluster_partition_handling: "pause_minority"` (`:86`), HA policy settings (`:91-107`). `rabbitmq_hostname`,
unused in Ussuri, no longer exists (no match in `ansible/`).

**Erlang cookie:** comes from `passwords.yml` keys `rabbitmq_cluster_cookie` / `outward_rabbitmq_cluster_cookie`
(`etc/kolla/passwords.yml:220,222`). It is passed to the broker container as the env `RABBITMQ_CLUSTER_COOKIE`
(`defaults/main.yml:11,15`). The `common` role also writes `rabbitmq_cluster_cookie` (main cluster only) to
`{{ node_config_directory }}/kolla-toolbox/rabbitmq-erlang.cookie`, which `kolla_toolbox` copies to
`/var/lib/rabbitmq/.erlang.cookie` at every `COPY_ALWAYS` start; a change notifies `Restart kolla-toolbox container`
(`roles/common/tasks/config.yml:211-221`, `roles/common/templates/kolla-toolbox.json.j2:4-9`). That happens only when
the `common` play runs (an untagged run or `-t common`, `site.yml:86-97`). The kolla image writes
`/var/lib/rabbitmq/.erlang.cookie` **only** when `KOLLA_BOOTSTRAP` is set, then exits; a normal start only handles the
log dir (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-26`; see
[Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)). That
happens only in the `{{ project_name }}_bootstrap` container, which runs only when the volume was just created
(`tasks/bootstrap.yml:26`). A normal start does not touch the cookie, and the file persists in the `{{ project_name }}`
volume (`defaults/main.yml:74`). Because the cookie is in the env, `compare_container` (env compare) still picks up a
cookie change and causes a **batched** recreate, but the recreated brokers keep their old `.erlang.cookie` file. NOT
AVAILABLE (it depends on whether `rabbitmq-server` itself reads `RABBITMQ_CLUSTER_COOKIE`, which is not in these
sources): whether a partition occurs during the roll, or whether the change is instead silently not applied to existing
brokers while `kolla_toolbox` (used by the drain step and by `service-rabbitmq`) and any broker bootstrapped later on a
fresh volume get the new cookie and cannot talk to the existing nodes.

### 2.3 Task flow per `kolla_action`

| Action | Flow | Evidence |
|---|---|---|
| **deploy** | `version-check.yml` (fails on a RabbitMQ downgrade, `run_once`, tag `rabbitmq-version-check`) -> `remove-ha-all-policy.yml` (only when `om_enable_rabbitmq_high_availability` is false, the default) -> `config.yml` -> `check-containers.yml` -> `bootstrap.yml`; handlers at the end of the role play; then the restart play and post-configuration (`enable_feature_flag all`) | `roles/rabbitmq/tasks/deploy.yml:1-12`, `version-check.yml:1-53`, `remove-ha-all-policy.yml:1-29`; `group_vars/all.yml:229`; `rabbitmq.yml:26-58` |
| **reconfigure** | = deploy | `tasks/reconfigure.yml:2` |
| **bootstrap.yml** | `create_volume {{ project_name }}`. **Only when the volume was just created** on that host: run `{{ project_name }}_bootstrap` with `bootstrap_environment`, `detach: False` | `roles/rabbitmq/tasks/bootstrap.yml:1-26` |
| **upgrade** | `remove-ha-all-policy.yml` (as above) -> `config.yml` -> `feature-flags.yml` (on the running brokers, before their restart) -> `check-containers.yml`; then the restart play (drained, batched) and post-configuration. There is no bootstrap step and **no cluster-wide stop** | `roles/rabbitmq/tasks/upgrade.yml:1-10` |
| **deploy-containers** | `check-containers.yml` only. Handlers at the end of the role play, then the restart play | `tasks/deploy-containers.yml` |
| **pull** | `service-images-pull` | `tasks/pull.yml` |
| **stop** | `service-stop`: all nodes **at once** | `tasks/stop.yml` |
| **precheck** | group check, free ports for both clusters, and `getent ahostsv4/6 <hostname>` for every rabbit host, failing unless every line resolves to that host's api IP (nodename `rabbit@<hostname>`); TLS files when TLS is on; with `om_enable_rabbitmq_high_availability` it asserts that an `ha-all` policy exists, with `om_enable_rabbitmq_quorum_queues` that every queue is a quorum queue | `roles/rabbitmq/tasks/precheck.yml:1-254` (`:62-78,152-171,202-254`) |
| **check** | **empty file**; `tools/kolla-ansible` 2023.1 has no `check` command | `tasks/check.yml:1` |
| **config** | `config.yml`. The handler is guarded by `kolla_action != "config"` | `handlers/main.yml:5-6` |

### 2.4 Config files (`ansible/roles/rabbitmq/tasks/config.yml`)

All files go into `/etc/kolla/{{ project_name }}/`. Except `config.json`, each file uses **`with_first_found`**, which
means a **full replacement** of the template, not a merge:
`/etc/kolla/config/rabbitmq/<inventory_hostname>/<file>` -> `/etc/kolla/config/rabbitmq/<file>` -> the role template.
All of them notify **`Restart rabbitmq container`**.

| File | Template highlights | Lines |
|---|---|---|
| `config.json` | `rabbitmq.json.j2`: `/usr/sbin/rabbitmq-server`. Copies the config files and, on every `COPY_ALWAYS` start, recursively chowns `/var/lib/rabbitmq` (the `{{ project_name }}` volume, mnesia included) and `/var/log/kolla/{{ project_name }}`, one `chown` per directory and file (`templates/rabbitmq.json.j2:53-64`; kolla `docker/base/set_configs.py:379-385,534-541`) | `config.yml:15-26` |
| `rabbitmq-env.conf` | `RABBITMQ_NODENAME=rabbit@<hostname>`, `RABBITMQ_DIST_PORT=role_rabbitmq_cluster_port`, `RABBITMQ_PID_FILE`, `ERL_EPMD_ADDRESS=api ip`, `ERL_EPMD_PORT=role_rabbitmq_epmd_port` | `config.yml:28-44`; `templates/rabbitmq-env.conf.j2:1-10` |
| `rabbitmq.conf` | `listeners.tcp.1 = api_ip:role_rabbitmq_port` (`listeners.ssl.1` with TLS); **`cluster_partition_handling = pause_minority`**; management listener; `management.load_definitions = /etc/rabbitmq/definitions.json`; `cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config` with every host in `groups[role_rabbitmq_groups]` | `config.yml:46-62`; `templates/rabbitmq.conf.j2:3-21` |
| `erl_inetrc` | `{inet6,true}` for IPv6 | `config.yml:64-80` |
| `advanced.config` | `inet_dist_use_interface` and `inet_dist_listen_min/max = role_rabbitmq_cluster_port` | `config.yml:82-98`; `templates/advanced.config.j2` |
| `definitions.json` | vhost `/` (plus the murano agent vhost for outward); user `role_rabbitmq_user` (administrator) plus an optional monitoring user (plus the murano agent user for outward). **Policies: none by default.** Only with `om_enable_rabbitmq_high_availability` (default `false`) is there an `ha-all` policy, on queues other than `amq.*`, `*_fanout_*` and `reply_*`, with `ha-mode: exactly` and `ha-params` = N // 2 + 1, `ha-promote-on-shutdown: always`, a 10 min message TTL and a 1 h queue expiry | `config.yml:100-116`; `templates/definitions.json.j2:1-28` (policies `:19-27`); `defaults/main.yml:91-107`; `group_vars/all.yml:229` |
| `enabled_plugins` | `rabbitmq_management`, plus `rabbitmq_prometheus` when Prometheus is enabled | `config.yml:118-134`; `defaults/main.yml:113-120` |

**Oddity:** the override paths are hard-coded to `/etc/kolla/config/rabbitmq/...` and do **not** include
`{{ project_name }}`. A custom `rabbitmq.conf` placed there replaces the template for **both** `rabbitmq` and
`outward_rabbitmq`, including the listener and management ports. NOT AVAILABLE: whether the two brokers on one host
would then try to bind the same ports (`config.yml:37-38,55-56,...`).

### 2.5 Handlers (`ansible/roles/rabbitmq/handlers/main.yml`), in definition order

| # | Name | listen | Logic | Lines |
|---|---|---|---|---|
| 1 | Restart rabbitmq container | (name) | `group_by {{ project_name }}_restart`, unless `kolla_action == "config"` | `:2-6` |

The Ussuri pair "Restart first rabbitmq container" / "Restart remaining rabbitmq containers" is gone: there is no
first-node-first rule any more.

`restart_services.yml` (run by the restart plays): `kolla_container_facts rabbitmq` -> if that container is running,
**put the node into maintenance mode** (`community.rabbitmq.rabbitmq_upgrade` `action: drain`, through `kolla_toolbox`)
-> `recreate_or_restart_container` (with env) ->
`docker exec <c> rabbitmqctl wait --timeout 60 /var/lib/rabbitmq/mnesia/rabbitmq.pid`. There is **no cluster-membership,
partition or mirror-sync check** (`roles/rabbitmq/tasks/restart_services.yml:1-39`;
`library/kolla_container_facts.py:77` lists running containers only).

**Rolling semantics (FACT, from the plays and the Ansible source):** `Restart rabbitmq services` runs
`restart_services.yml` on the hosts of `rabbitmq_restart` in `serial: "33%"` batches (`rabbitmq.yml:26-41`): **one node
at a time** with up to 6 notified nodes, 2 with 7 to 9 (section 0). Restart time grows linearly with N. Only notified
hosts are in the group. If every host of a batch fails (for example the `--timeout 60` wait), the playbook stops before
the next batch (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:204-208`). NOT AVAILABLE: the order of
the batches, which follows the order in which `group_by` added the hosts
(`lib/ansible/plugins/strategy/__init__.py:667-669`).

**Oddity:** `restart_services.yml` checks for a container named `rabbitmq` (`:6`), and `feature-flags.yml` runs
`docker exec rabbitmq` (`feature-flags.yml:3`), whatever `project_name` is; `remove-ha-all-policy.yml` calls
`docker exec` literally instead of `kolla_container_engine` (`:14,20`). NOT AVAILABLE: which broker the drain step of
the outward restart play talks to, since the `rabbitmq_upgrade` module runs in `kolla_toolbox`, whose cookie is the main
cluster's.

### 2.6 Bootstrap and registration

- The cluster/user bootstrap is declarative. Users, vhosts and policies come only from `definitions.json`, which is
  loaded at node boot (`rabbitmq.conf.j2:13`). There is no `rabbitmq_user` task in the role, so a **changed
  `rabbitmq_password` takes effect only through a restart** (batched, via the restart play). The role's `rabbitmqctl`
  calls are limited to the version check, the `ha-all` removal, feature flags, the wait and `reset-state`
  (`version-check.yml:14`, `remove-ha-all-policy.yml:14,20`, `feature-flags.yml:3`, `restart_services.yml:39`,
  `reset-state.yml`).
- The `{{ project_name }}_bootstrap` container runs only on hosts whose volume is newly created (`bootstrap.yml:26`). It
  does not re-run on reconfigure.
- Per-service users and vhosts are created only by the `service-rabbitmq` role
  (`roles/service-rabbitmq/tasks/main.yml:1-47`, `update_password: always`), which in 2023.1 is used only by `nova-cell`
  (`roles/nova-cell/tasks/rabbitmq.yml:5,15`). Every other service shares the `openstack` user on vhost `/`
  (`group_vars/all.yml:205-222`).

### 2.7 Dependencies

- **Explicit:** none in role metadata (no `meta/`).
- **Implicit:**
  - Hostnames must resolve to the api IP on every node (precheck), because nodenames are `rabbit@<hostname>`.
  - Facts (`hostname`).
  - `kolla_toolbox` (from `common`) for the drain step and `service-rabbitmq`.
  - HAProxy, only for the management UI and the outward external port.
- **Consumers:** the templates of 30 roles render `rpc_transport_url` (31 roles reference some `transport_url`), which
  lists **every** host in `groups['rabbitmq']` (`group_vars/all.yml:212,222`;
  `grep -l rpc_transport_url roles/*/templates`). Keystone is one of them (`keystone.conf.j2:4,54`).

### 2.8 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a config change** drains and restarts the brokers in `serial: "33%"` batches, one node at a time
   with up to 6 nodes. At most one node is down at a time in that case, so a 3-node cluster keeps 2/3 and stays above
   the `pause_minority` threshold. The restart only runs `rabbitmqctl wait --timeout 60` and has no mirror-sync check
   (`restart_services.yml:9-39`). Mirroring is off by default (`om_enable_rabbitmq_high_availability: false`,
   `group_vars/all.yml:229`; empty `policies`, `definitions.json.j2:25-27`), and deploy removes an existing `ha-all`
   policy (`remove-ha-all-policy.yml:18-22`). NOT AVAILABLE: what happens to the queues of a drained node without
   mirroring, and, with mirroring enabled, whether the next node may be stopped while mirrors on the freshly restarted
   node are still unsynchronised.
2. **Upgrade = full outage of the message bus** no longer holds in 2023.1. `upgrade.yml` has no stop step
   (`roles/rabbitmq/tasks/upgrade.yml:1-10`); an image change goes through the same drained, batched restart play as a
   reconfigure (`rabbitmq.yml:26-41`). A downgrade is refused by `version-check.yml` on deploy/reconfigure
   (`version-check.yml:37-44`; `deploy.yml:2`), not on `upgrade` (`upgrade.yml` does not import it). NOT AVAILABLE:
   whether clients lose RPC while each node is drained and restarted.
3. **Uncontrolled full stop** (`kolla-ansible stop`, power loss) followed by deploy: the brokers come back through the
   batched restart play, one batch after another, each waiting `rabbitmqctl wait --timeout 60`. The drain step is
   skipped for a stopped container (`restart_services.yml:17`). Which node starts first is NOT AVAILABLE (`group_by`
   order). NOT AVAILABLE (RabbitMQ semantics): whether a node that was not the last to stop waits for its peers' Mnesia
   tables longer than 60 s. FACT: if it does, the wait fails, and with one node per batch (up to 6 nodes) the playbook
   stops before the other nodes are started (section 0).
4. **Scaling the rabbitmq group changes `transport_url` in about 30 services**, so it restarts almost every OpenStack
   service cloud-wide when those plays run. It also changes `rabbitmq.conf` (classic_config node list) on every broker,
   which causes a batched restart.
5. **Password change.** `definitions.json` changes cause a batched broker restart in the rabbitmq plays. Consumers get
   the new password only when their own plays run later in `site.yml`. NOT AVAILABLE: whether there is an auth-failure
   window in between.
6. **Bug (FACT): `kolla-ansible pull` with outward rabbitmq enabled.** The outward plays set
   `project_name: outward_rabbitmq` and no `kolla_role_name` (`rabbitmq.yml:71`), so `service-images-pull` looks up
   `lookup('vars', (kolla_role_name | default(project_name)) + '_services')` = `outward_rabbitmq_services`, and that
   variable is not defined anywhere (`roles/service-images-pull/tasks/main.yml:14`; `grep outward_rabbitmq_services`
   finds nothing). The `vars` lookup raises an undefined-variable error for a name it cannot find when no default is
   given, so "Pull images" fails on the outward-rabbitmq hosts (ansible-core 2.14.18
   `lib/ansible/plugins/lookup/vars.py:94-104`).
7. `check.yml` is empty. `rabbitmq_hostname` no longer exists in 2023.1.
8. The precheck runs `getent` for every rabbit host on every rabbit host, so it does N² lookups
   (`precheck.yml:62-69,152-161`).

---

## 3. Keystone (`ansible/roles/keystone`)

### 3.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial |
|---|---|---|---|---|
| loadbalancer -> `include_role keystone tasks_from: loadbalancer` | `site.yml:198-202` | loadbalancer | `keystone` | loadbalancer serial |
| `Apply role keystone` | `site.yml:450-458` | `keystone` + `&enable_keystone_True` | `keystone` | **`serial: '{{ kolla_serial\|default("0") }}'`** (`:455`) |

What serial means here:
- With the default (`ANSIBLE_SERIAL` unset, so 0 = all hosts), every keystone node is handled in **one batch**
  (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:300-302`), and handlers restart **all keystone
  containers at once** (section 0, "Handler order").
- With `ANSIBLE_SERIAL=n`, `run_once` tasks run **once per batch**: bootstrap container (db_sync), key distribution,
  register. Each batch is a separate run on the inventory restricted to that batch, and `run_once` sends a task only to
  the first host left (`playbook_executor.py:184-189`, `lib/ansible/plugins/strategy/linear.py:217,246-248`).
- Fernet bootstrap is blocked when not all hosts are in the batch (3.6).
- On upgrade, `Init` (expand/migrate) runs in the batch containing `groups['keystone'][0]` and `Finish` (contract) runs
  in the batch containing `groups['keystone'][-1]`.

### 3.2 `keystone_services` (`ansible/roles/keystone/defaults/main.yml:2-55`)

In 2023.1 the dict spans `roles/keystone/defaults/main.yml:2-66` (the heading keeps its earlier range so that links stay
stable).

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `keystone` | `keystone` | `keystone` | `true` | Apache + mod_wsgi. Volumes include **`keystone_fernet_tokens:/etc/keystone/fernet-keys`** (`:163-169`). HAProxy `keystone_internal` (5000), `keystone_external` (5000, external), and `keystone_admin` (35357) **only when `kolla_action == 'upgrade'`** ("kept only for upgrade compatibility") (`:11-40`). Healthcheck `healthcheck_curl` on port 5000 (`:124-135`) |
| `keystone-ssh` | `keystone_ssh` | `keystone` | `true` | `sshd -D` on `api_interface_address:8023` (`templates/sshd_config.j2:1-2`, `group_vars/all.yml:377`). Shares the `keystone_fernet_tokens` volume (`:51`) |
| `keystone-fernet` | `keystone_fernet` | `keystone` | `true` | Runs cron with the rotation crontab. Healthcheck `fernet-healthcheck.sh` = `fernet-node-sync.sh --check && fernet-push.sh --check` (`:154-161`; `templates/fernet-healthcheck.sh.j2:6`). Shares the `keystone_fernet_tokens` volume (`:64`) |

There is no `keystone_token_provider` in 2023.1: `keystone.conf` sets `provider = fernet` unconditionally
(`templates/keystone.conf.j2:32`), and the ssh and fernet containers are always enabled.

Relevant globals (`ansible/group_vars/all.yml`):

| Variable | Value | Line |
|---|---|---|
| `fernet_token_expiry` | 86400 | `:882` |
| `fernet_token_allow_expired_window` | 172800 | `:884` |
| `fernet_key_rotation_interval` | expiry + window = 259200 s (3 days) | `:889` |
| `keystone_admin_url` | `keystone_internal_url` (`internal_protocol://<internal VIP>:5000`) | `:864-865` |
| `openstack_auth.auth_url` | `keystone_internal_url` | `:895-899` |
| `multiple_regions_names` | `[openstack_region_name]` | `:595-596` |
| `keystone_default_user_role` | `member` | `:891` |

### 3.3 Task flow per `kolla_action`

| Action | Flow | Evidence |
|---|---|---|
| **deploy** | `config.yml` -> `check-containers.yml` -> `clone.yml` (dev mode only) -> `bootstrap.yml` -> `flush_handlers` -> `distribute_fernet.yml` -> `register.yml` -> `register_identity_providers.yml` (federation only) | `roles/keystone/tasks/deploy.yml:1-21` |
| **reconfigure** | = deploy, so **bootstrap, distribution and registration all re-run** | `roles/keystone/tasks/reconfigure.yml:2` |
| **upgrade** | `config.yml` -> `check-containers.yml` -> set `log_bin_trust_function_creators=1` (`run_once`, on `groups['keystone'][0]`) -> notify `Init keystone database upgrade` on `[0]` -> notify `Finish keystone database upgrade` on `[-1]` -> `flush_handlers` -> set `log_bin_trust_function_creators=0` (`run_once`, every batch) -> `service-ks-register`, which removes the admin endpoint (`state: absent`). **No** bootstrap or key distribution | `roles/keystone/tasks/upgrade.yml:1-59`; `defaults/main.yml:209-212` |
| **deploy-containers** | `check-containers.yml` | `tasks/deploy-containers.yml` |
| **pull / stop** | `service-images-pull` / `service-stop` (all 3 containers, all hosts at once) | `tasks/pull.yml`, `tasks/stop.yml` |
| **precheck** | group check; free ports 5000 and 8023; **assert `fernet_token_expiry` is an int between 0 and 604800** | `roles/keystone/tasks/precheck.yml:1-60` |
| **check** | No `check.yml` in the role, no `kolla_enable_sanity_*` variable and no `check` command in `tools/kolla-ansible` 2023.1 | `ls roles/keystone/tasks` |
| **config** | `config.yml`. Handlers are guarded by `kolla_action != "config"` | `handlers/main.yml:42-43,58-59,74-75` |

`bootstrap.yml` and `bootstrap_service.yml` (run on **every deploy/reconfigure**):
1. `mysql_db keystone` and `mysql_user keystone` with `keystone_database_password`, `append_privs` (`run_once`,
   `delegate_to: groups['keystone'][0]`, skipped with `use_preconfigured_databases`)
   (`roles/keystone/tasks/bootstrap.yml:1-36`). This re-asserts the DB user password on each run.
2. `kolla_container_facts keystone_fernet` (lists *running* containers only, `library/kolla_container_facts.py:77`) ->
   `group_by keystone_fernet_<State|bootstrap>` (`roles/keystone/tasks/bootstrap_service.yml:2-18`).
3. Fail if no host has `keystone_fernet` running and not every keystone host is in `ansible_play_batch` ("Please run
   without --limit or --serial") (`:22-31`).
4. **`bootstrap_keystone` container** (`KOLLA_BOOTSTRAP`). In the kolla image, `kolla_start` sources
   `kolla_extend_start`, which sees `KOLLA_BOOTSTRAP`, runs `sudo -H -u keystone keystone-manage db_sync` and exits 0
   without starting httpd (kolla `docker/base/start.sh:18-21`, `docker/keystone/keystone/extend_start.sh:41-46`; see
   [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)).
   `EXTRA_KEYSTONE_MANAGE_ARGS` is empty by default (kolla `docker/keystone/keystone/extend_start.sh:21`) and
   kolla-ansible does not set it. It is `run_once` without `delegate_to` (first host of the batch) and runs **on every
   deploy/reconfigure** (`bootstrap_service.yml:33-50`).
5. `bootstrap_keystone_fernet`: `keystone-manage fernet_setup`, `run_once`, `delegate_to: groups['keystone'][0]`, **only
   if no `keystone_fernet` container is running on any play host** (`:52-75`).

`distribute_fernet.yml` (every deploy/reconfigure):
- Wait for port 8023 on every host (`:2-10`).
- **`docker exec -t keystone_fernet /usr/bin/fernet-push.sh`**, `run_once`, `delegate_to` = the first host in
  `keystone_fernet_running` (or `groups['keystone'][0]` on first bootstrap) (`:12-18`).

`register.yml` (every deploy/reconfigure):
- `docker exec keystone kolla_keystone_bootstrap <admin user> <admin pw> <project> admin <internal_url> <public_url> <region>`, once per region (`run_once`); no admin URL any more (`roles/keystone/tasks/register.yml:2-12`).
- `service-ks-register` for the identity service and its endpoints (internal, public; admin `state: absent`) and the
  `service` role (`:14-20`; `defaults/main.yml:209-221`).
- `os_keystone_role` `keystone_default_user_role` (`member`) (`:22-33`).

### 3.4 Config files (`ansible/roles/keystone/tasks/config.yml`)

| Destination (`/etc/kolla/...`) | Source / merge order | Notifies | Lines |
|---|---|---|---|
| `<svc>/config.json` | `keystone.json.j2` / `keystone-ssh.json.j2` / `keystone-fernet.json.j2` | `Restart <svc> container` | `:45-56` |
| `keystone/keystone.conf`, `keystone-fernet/keystone.conf` | `merge_configs`: `templates/keystone.conf.j2` + `/etc/kolla/config/global.conf` + `/etc/kolla/config/keystone.conf` + `/etc/kolla/config/keystone/<svc>.conf` + `/etc/kolla/config/keystone/<host>/keystone.conf` | `Restart keystone container` / `Restart keystone-fernet container` | `:58-77` |
| `keystone/keystone-startup.sh` | template. Waits up to 36 x 5 s (**3 min**) for fernet key `0`, then `exec httpd/apache2` | `Restart keystone container` | `:79-91`; `templates/keystone-startup.sh.j2:9-24` |
| `keystone/domains/*` | Created only if `/etc/kolla/config/keystone/domains` exists on the controller. Every file in it is **templated** (Jinja) into `/etc/kolla/keystone/domains/`. `keystone.conf` gains `[identity] domain_specific_drivers_enabled = true, domain_config_dir = /etc/keystone/domains` | `Restart keystone container`. A file added once `keystone.conf` already has the domain settings is not yet in the container and the `domains` entry is optional, so `kolla_set_configs --check` exits 2 and "Check keystone containers" fails on every keystone host before the handler runs (`templates/keystone.json.j2:25-31`, `tasks/deploy.yml:2-4`, `module_utils/kolla_docker_worker.py:155-190`; [Kolla images §3.3](../../concepts/kolla-images.md#33-exit-codes)) | `:34-39,93-130`; `keystone.conf.j2:24-28` |
| `<keystone, keystone-fernet>/<policy file>` | First found in `/etc/kolla/config/keystone/` (`supported_policy_format_list`) | `Restart <svc> container` | `:15-32,132-145` |
| `keystone/wsgi-keystone.conf` | `with_first_found`: `/etc/kolla/config/keystone/<host>/wsgi-keystone.conf` -> `/etc/kolla/config/keystone/wsgi-keystone.conf` -> template. `processes = keystone_api_workers` = `openstack_service_workers` = min(vCPU, 5) (`defaults/main.yml:180`, `group_vars/all.yml:598`) | `Restart keystone container` | `:151-167`; `templates/wsgi-keystone.conf.j2:47` |
| `keystone/keystone-paste.ini` | Only if `/etc/kolla/config/keystone/keystone-paste.ini` exists | `Restart keystone container` | `:169-193` |
| (controller) cron generator | `python fernet_rotate_cron_generator.py -t <interval_s//60> -i <index in groups['keystone']> -n <len>`, `delegate_to: localhost`, per host | none (`changed_when: false`) | `:195-210` |
| `keystone-fernet/{crontab, fernet-rotate.sh, fernet-node-sync.sh, fernet-push.sh, fernet-healthcheck.sh, id_rsa, ssh_config}` | templates (`id_rsa` = `{{ keystone_ssh_key.private_key }}`) | `Restart keystone-fernet container` | `:212-233` |
| `keystone-ssh/{sshd_config, id_rsa.pub}` | templates (`id_rsa.pub` becomes `authorized_keys`) | `Restart keystone-ssh container` | `:235-250` |

`keystone.conf.j2` highlights:
- `transport_url = rpc_transport_url` (`:4`).
- `[database] connection` via the VIP, `max_retries = -1` (`:18-22`).
- `[token] provider = fernet`, `expiration`, `allow_expired_window` (`:30-34`).
- `[fernet_tokens] max_active_keys = ceil((expiry + window) / rotation_interval) + 2`, which is **3** with the defaults
  (`:43-46`).
- `[cache] backend = oslo_cache.memcache_pool`, `memcache_servers` = every `groups['memcached']` host (`:48-51`).
- `[oslo_messaging_notifications]` uses `notify_transport_url` and driver `messagingv2` only when ceilometer or barbican
  topics are enabled, otherwise `noop` (`:53-60`; `defaults/main.yml:194-203`).

### 3.5 Handlers (`ansible/roles/keystone/handlers/main.yml`). Order is load-bearing (comment `:2-3`)

| # | Name | Logic | Lines |
|---|---|---|---|
| 1 | Init keystone database upgrade | `init_upgrade_database` container, `KOLLA_UPGRADE`, `run_once`, only when `kolla_action == upgrade` and the host is `groups['keystone'][0]` | `:5-27` |
| 2 | Restart keystone-ssh container | `recreate_or_restart_container`. All notified hosts in the batch **in parallel** | `:29-43` |
| 3 | Restart keystone-fernet container | same | `:45-59` |
| 4 | Restart keystone container | same: **no rolling, no wait for port or health** | `:61-75` |
| 5 | Finish keystone database upgrade | `finish_upgrade_database`, `KOLLA_FINISH_UPGRADE`, `run_once`, `kolla_action == upgrade`. No host guard: it relies on being notified only on `groups['keystone'][-1]` (`upgrade.yml:28-31`) | `:77-98` |

### 3.6 Fernet key lifecycle (FACT unless marked)

- **Storage:** a per-host Docker volume `keystone_fernet_tokens`, shared by the `keystone`, `keystone_fernet` and
  `keystone_ssh` containers (`defaults/main.yml:51,64,169`).
- **Initial setup:** `keystone-manage fernet_setup` on `groups['keystone'][0]` only when no `keystone_fernet` container
  is *running* anywhere in the play (`bootstrap_service.yml:52-75`). The code comment admits the detection is imprecise:
  "This does not catch some cases ... the keystone_fernet container is created but not running ... Probably what we care
  about is the existence of Fernet key 0" (`:10-14`). NOT AVAILABLE (Keystone upstream behaviour): whether
  `fernet_setup` is a no-op when key `0` already exists, which would make a re-run on a node with an intact volume
  harmless. On a **rebuilt `groups['keystone'][0]`** (empty volume), with every `keystone_fernet` container stopped (for
  example after `kolla-ansible stop`), a deploy runs `fernet_setup` on that node and then **pushes its key set with
  `rsync --delete` to every node** (`:52-75`; `distribute_fernet.yml:12-18`; `templates/fernet-push.sh.j2:17-22`). NOT
  AVAILABLE: whether `fernet_setup` then generates brand-new keys and whether that invalidates all tokens; the code
  comment at `bootstrap_service.yml:20-21` names this risk.
- **Rotation:** cron in `keystone_fernet` runs `fernet-rotate.sh` = `keystone-manage fernet_rotate` && `fernet-push.sh`
  (`templates/fernet-rotate.sh.j2:6-8`). `fernet-push.sh` runs, for each other keystone host,
  `rsync -az ... --delete /etc/keystone/fernet-keys/ keystone@<host>:/etc/keystone/fernet-keys` over ssh port 8023,
  under `set -o errexit` (`templates/fernet-push.sh.j2:3,17-22`). With `--check` it does the same as a dry run, which
  the container healthcheck uses (`:6-15`).
- **Schedule:** the generator gives each host a weekly crontab (min hour * * dow) in round-robin with offset
  `interval * index` (`files/fernet_rotate_cron_generator.py:39-94`; `templates/crontab.j2:5-7`). It deliberately
  under-rotates across the week boundary (`:53-54,67`). Working through `generate()` by hand for these inputs, which all
  take the day branch (offset `interval * index`, step `interval * hosts`, a job only while `time + interval <= 10080`;
  `:55-56,65-73`), gives:

  | Interval | Hosts | Result |
  |---|---|---|
  | 4320 min (default 3 days) | 3 | h0 = `Sun 00:00`, h1 = `Wed 00:00`, **h2 = no jobs**. Gaps 3 d / 4 d |
  | 4320 min | 5 | only h0 and h1 have jobs |
  | 1440 min | 3 | h0 Sun/Wed/Sat, h1 Mon/Thu, h2 Tue/Fri |

  Crons run in the container's local time (`/etc/localtime` is mounted, `defaults/main.yml:61`).
- **Distribution on every deploy/reconfigure:** `fernet-push.sh` runs from the first running node
  (`distribute_fernet.yml:12-18`), so that node's key set **overwrites** every other node (`--delete`).

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
  `keystone` and the region (`:46`). It counts eight 'already exists'/'exists'/'already has'/'skipping' patterns
  (domain, project, user, role, role assignment, region, internal and public endpoints) but reports unchanged only when
  the count is nine (`:51-63`). NOT AVAILABLE (upstream `keystone-manage bootstrap` is not in these sources): whether
  any output line matches twice, so that the task can ever report unchanged; whether `keystone-manage bootstrap`
  re-asserts the admin user, project, role and endpoints and **resets the admin password to `keystone_admin_password`**
  if it differs. The wrapper has no pattern for a password reset (`:51-63`).
- `service-ks-register` (identity service and endpoints)
- the `member` role

All of these are `run_once` per batch, except the cron generator, which runs on the controller once per host.

### 3.8 Dependencies

- **Explicit:** none in role metadata (no `meta/`).
- **Implicit, upstream:**
  - **MariaDB** via the VIP (`keystone_database_address`, `defaults/main.yml:80`).
  - **memcached**: `[cache]` (`keystone.conf.j2:48-51`). The memcached play (`site.yml:387`) runs before keystone
    (`:450`).
  - **RabbitMQ**: `transport_url` is always rendered, and notifications go out only if ceilometer or barbican is enabled
    (`keystone.conf.j2:4,53-60`).
  - **HAProxy VIP**: `keystone_internal_url` is used by `openstack_auth` for registration
    (`group_vars/all.yml:895-899`).
  - **kolla_toolbox** (`os_*` modules).
  - `passwords.yml` `keystone_ssh_key` (`etc/kolla/passwords.yml:192`).
- **Downstream:** see 3.10.

### 3.9 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a config change** (default serial 0) restarts `keystone_ssh`, then `keystone_fernet`, then
   `keystone`, each **on all keystone hosts simultaneously** (handlers `:29-75`). The result is a brief **Keystone-wide
   API outage**. Nothing waits for the API to return before `register.yml` runs (which uses `run_once` plus
   `until`/retries inside `service-ks-register`, `roles/service-ks-register/tasks/main.yml:21-23`). The containers have
   a healthcheck (`defaults/main.yml:124-135`), but the handlers do not wait for it. NOT AVAILABLE: whether other
   services keep validating cached tokens via memcached during the restart. Set `ANSIBLE_SERIAL` for a rolling
   reconfigure.
2. **What restarts keystone indirectly.** `keystone.conf` embeds every memcached host and every rabbitmq host
   (`keystone.conf.j2:4,51,54`), and the fernet crontab and `fernet-push.sh` embed the keystone host list and index.
   Adding or removing a memcached, rabbitmq or keystone node therefore restarts keystone, and keystone-fernet as well
   for keystone node changes.
3. **Fernet push has no partial-failure handling.** `set -o errexit` stops at the first unreachable peer, so later peers
   are not updated either (`fernet-push.sh.j2:3,17-22`). The next scheduled rotation runs on another node (round-robin,
   3.6), which may be one of the peers left with the *stale* set. That node runs `fernet_rotate` and then
   `fernet-push.sh`, whose `rsync --delete` overwrites the key set of each peer it reaches, stopping at the first
   failure (`templates/fernet-rotate.sh.j2:6-8`, `templates/fernet-push.sh.j2:3,17-22`). The reconfigure-time push from
   "first running node" works the same way. The `keystone_fernet` healthcheck (`fernet-push.sh --check`) reports such a
   failure as unhealthy (`templates/fernet-healthcheck.sh.j2:6`). NOT AVAILABLE (Keystone key handling): whether this
   removes the key that signed live tokens and so causes mass 401s.
4. **Bug in the cron generator hour calculation.** In the day branch, `hour = time % HOUR_SPAN` is computed where
   `(time % DAY_SPAN) // HOUR_SPAN` was intended (`fernet_rotate_cron_generator.py:68-70`). It is harmless when the
   interval is a whole number of days (the default). Otherwise it can **over-rotate**. Read from the code: with interval
   3600 min (60 h, i.e. `fernet_token_expiry=43200`), h1 has `time = 3600`, so `day = 2` and `hour = 3600 % 60 = 0`,
   giving `day 2 00:00` instead of `day 2 12:00` after h0's `day 0 00:00`, which is a **48 h gap with a 60 h interval**.
   NOT AVAILABLE (Keystone key handling): whether, with `max_active_keys=3`, a key can then be deleted before the
   allow-expired window of tokens it signed has elapsed.
5. **The precheck validates the wrong variable.** It asserts `fernet_token_expiry <= 604800` (`precheck.yml:43-60`, and
   its message talks about "rotate the fernet keys"). The generator, however, is fed `fernet_key_rotation_interval` (=
   expiry + 2 d by default, `config.yml:196-199`) and fails above 10080 min (`generator:59-62`). The generator exits 0
   with `{"failed": true}` (`:31-36,116-117`), so the `command` task succeeds and **`set_fact cron_jobs` then errors on
   a missing key** (`config.yml:207-210`). Any `fernet_token_expiry` above 5 days with the default window passes
   precheck but breaks deploy.
6. **Under-rotation by design.** With 3 or more hosts and the 3-day default, only 2 hosts ever rotate. Rotations happen
   at a fixed local `00:00` on Sunday and Wednesday.
7. **Shared SSH key.** Every node gets the same `keystone_ssh_key`, and `ssh_config` sets `StrictHostKeyChecking no`,
   `UserKnownHostsFile /dev/null` (`templates/ssh_config.j2:1-4`). NOT AVAILABLE: whether anyone holding the private key
   and reaching port 8023 on the API network can overwrite fernet keys as `fernet-push.sh` does
   (`templates/fernet-push.sh.j2:20`), and whether that allows token forgery.
8. **Domain config cleanup.** Removing a file from `/etc/kolla/config/keystone/domains` is never propagated: no task
   deletes stale files in `/etc/kolla/keystone/domains/`. FACT: under the default `COPY_ALWAYS` the stale file is copied
   back into the container at every start, even after a recreate: `domains` is a directory entry
   (`templates/keystone.json.j2:25-31`), so `kolla_set_configs` deletes `/etc/keystone/domains` and re-copies the whole
   host directory (kolla `docker/base/set_configs.py:136-158,534-541`; see
   [Kolla images §2.3](../../concepts/kolla-images.md#23-kolla_set_configs-copy-and-permissions)). `keystone.conf` keeps
   `domain_specific_drivers_enabled = true` and `domain_config_dir = /etc/keystone/domains` while
   `/etc/kolla/config/keystone/domains` exists (`templates/keystone.conf.j2:24-28`). NOT AVAILABLE (Keystone semantics):
   whether Keystone keeps loading the stale file as a domain config. The task also re-uses the variable name
   `register: keystone_domains` (`config.yml:112,123`), which is an oddity.
9. **Upgrade.** Without serial, all keystone APIs restart at once between `Init` (expand/migrate) and `Finish`
   (contract). With serial, `log_bin_trust_function_creators` is reset to 0 at the end of **every** batch
   (`upgrade.yml:36-50`), while `Enable` runs only in the batch whose first host is `groups['keystone'][0]` (`:6-21`).
   The contract step in the last batch therefore runs with it disabled. Oddity; the impact is NOT AVAILABLE. The upgrade
   also removes the admin endpoint (`:52-59`).
10. **Reconfigure re-asserts identity state.** It re-applies the admin credentials and endpoints, and the DB user
    password, from `passwords.yml` and globals. NOT AVAILABLE (os_user and `keystone-manage bootstrap` semantics):
    whether out-of-band changes are silently reverted.

### 3.10 Runtime dependency of other services on Keystone (grep across `ansible/roles/*/templates`)

| Measure | Count | Pattern |
|---|---|---|
| Roles with `www_authenticate_uri` (keystonemiddleware `[keystone_authtoken]`) | **28** | `www_authenticate_uri = {{ keystone_internal_url }}` (30 lines); 30 roles have a `[keystone_authtoken]` section (sahara and venus without `www_authenticate_uri`) |
| Roles with `auth_url` | **37** | `auth_url = {{ keystone_internal_url }}` (75 lines), `{{ openstack_auth.auth_url }}` (1); no `/v3` and no admin-endpoint variants any more |
| Roles with `memcache_servers` / `memcached_servers` | **32** | (36 `memcached_servers =` lines + 7 `memcache_servers =`) |
| Roles with `memcache_secret_key` | **29** | Token cache in memcached with `memcache_security_strategy = ENCRYPT` (for example `roles/nova/templates/nova.conf.j2:112-127`) |
| Roles that call `service-ks-register` | **37** (keystone included) | During their deploy/reconfigure they create services, endpoints, users, roles and grants through `openstack_auth`, i.e. **`keystone_internal_url` on the internal VIP:5000** with `openstack_interface: internal`, `run_once`, 5 retries x 10 s (`roles/service-ks-register/tasks/main.yml:1-136`, `defaults/main.yml:1-41`; `group_vars/all.yml:609,895-899`) |

Implications:
- FACT: the `[keystone_authtoken]` sections of 30 roles point keystonemiddleware at Keystone, and 29 roles keep its
  token cache in memcached (`memcache_secret_key`). The Ussuri erratum on these counts
  ([erratum](index.md#verification-and-errata)) concerns the Ussuri tree; the counts above are a recursive grep of the
  2023.1 templates. NOT AVAILABLE: whether those API services fail to authenticate requests while Keystone or memcached
  is unavailable.
- Keystone, via the internal endpoint, is a **hard deploy-time dependency** for the `deploy`/`reconfigure` of 37 roles.
- Every service's `memcached_servers` and `transport_url` embed the full memcached and rabbitmq host lists, so changes
  to those groups fan out as restarts across the whole control plane.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
