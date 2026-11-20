---
title: Fact sheet B
description: "Fact sheet for MariaDB, RabbitMQ and Keystone: Galera bootstrap, recovery, backup and rolling restart, RabbitMQ, Keystone fernet keys."
tags: [mariadb, rabbitmq, keystone, mariadb-backup, mariadb-recovery, handlers]
---

# Fact sheet B

Source: `kolla-ansible` at tag `ussuri-eol` (verified with `git describe --tags`). Every path below is relative to the
repo root.
Labels: **FACT** = read directly from source code (cited): kolla-ansible, the kolla image repository (cited as kolla
`docker/...`) or Ansible (cited as ansible 2.9.27 `lib/ansible/...`). **NOT AVAILABLE** = these sources do not establish
it, often because it depends on upstream MariaDB, RabbitMQ, Keystone, HAProxy or Docker behaviour that is not in them.

The supported Ansible range is 2.8 to 2.9 (`ansible/roles/prechecks/vars/main.yml:4-5`). Statements about handler and
include semantics assume that range and cite the Ansible 2.9.27 source.

---

## 0. Shared context that applies to all three roles

| Topic | Fact | Evidence |
|---|---|---|
| Action dispatch | `tasks/main.yml` = `include_tasks: "{{ kolla_action }}.yml"`. rabbitmq adds `when: inventory_hostname in groups[role_rabbitmq_groups]` | `ansible/roles/mariadb/tasks/main.yml:2`, `ansible/roles/keystone/tasks/main.yml:2`, `ansible/roles/rabbitmq/tasks/main.yml:2-3` |
| `common` dependency | All three roles have `meta/main.yml` -> `dependencies: - { role: common }` | `ansible/roles/{mariadb,rabbitmq,keystone}/meta/main.yml:2-3` |
| `common_run` guard | The common role runs only `when: not common_run` and then sets `common_run: True`. The `mariadb_recovery` and `mariadb_backup` commands pass `-e common_run=true`, so common is skipped entirely | `ansible/roles/common/tasks/main.yml:4,8,10`; `tools/kolla-ansible:370,375` |
| Serial | `kolla_serial` is passed only for `upgrade` and `reconfigure`, from `ANSIBLE_SERIAL` (default 0 = all hosts). The comment says "Serial is not recommended and disabled by default" | `tools/kolla-ansible:234-236,430,439` |
| Config strategy | `config_strategy: "COPY_ALWAYS"`, so `recreate_or_restart_container` stops and starts the container when its parameters are unchanged | `ansible/group_vars/all.yml:43`; `ansible/library/kolla_docker.py:781-803` |
| Graceful stop | Effective stop timeout is **10 s**, not 60 s: `kolla_docker`'s `graceful_timeout` argument defaults to `10` and, being non-`None`, overrides `docker_common_options.graceful_timeout` (`docker_graceful_timeout: 60`). No task in these roles passes `graceful_timeout`, so every `kolla_docker` stop/restart (handlers and `recreate_or_restart_container` included) calls `docker stop` with a 10 s timeout (erratum in [Per-role fact sheets](index.md)). Docker's own stop behaviour (which signal, when it kills) is NOT AVAILABLE from these sources. For MariaDB the image runs `dumb-init` without `--single-child` (kolla `docker/mariadb/mariadb/Dockerfile.j2:65-76`). The image's comment says that mysqld_safe ignores SIGTERM and that, without `--single-child`, TERM is sent to all subprocesses, including mysqld (kolla `Dockerfile.j2:67-71`). NOT AVAILABLE: the dumb-init and mysqld_safe behaviour itself, and so whether mysqld gets the 10 s to shut down | `ansible/group_vars/all.yml:154,166`; `ansible/library/kolla_docker.py:871-884,892-903,991,1037-1047` |
| Bootstrap containers | `kolla_docker` defaults `remove_on_exit: True`, so `detach: False` bootstrap/upgrade containers are removed after they exit. Containers started with a `BOOTSTRAP` label are later recreated because `compare_labels` sees a difference | `ansible/library/kolla_docker.py:420-432,837-839`, arg defaults around `:979-1000` |
| `compare_environment` | Checks only that the *desired* env keys exist with equal values. Extra env vars on the running container (for example `BOOTSTRAP_ARGS`) are not detected; labels are what force the recreate | `ansible/library/kolla_docker.py:467-479` |
| Handler order | Ansible runs handlers in the order they are **defined in `handlers/main.yml`**, not in notify order, and queues each handler for every notified host before it waits for the results. This matters for the mariadb and keystone handlers below | ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:972-988,1019-1035` |
| Loadbalancer config | The haproxy play (`site.yml:126-392`) runs `include_role ... tasks_from: loadbalancer` for each service, only when `kolla_action in ['deploy','reconfigure','upgrade','config']` | `ansible/site.yml:390-392` |

Play order in `site.yml` (relevant subset): haproxy `:126` -> **mariadb `:471`** -> memcached `:481` -> **rabbitmq
`:535`** -> **outward rabbitmq `:555`** -> **keystone `:596`** -> everything else (glance `:657` onward). Keystone
therefore runs after its DB, cache and MQ dependencies, and before every service that registers with Keystone.

---

## 1. MariaDB (`ansible/roles/mariadb`)

### 1.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial | Notes |
|---|---|---|---|---|---|
| `Apply role haproxy` -> `include_role mariadb tasks_from: loadbalancer` | `ansible/site.yml:249-253` | `haproxy` + `&enable_haproxy_True` (`:126-131`) | `mariadb` | haproxy play has `serial: kolla_serial` (`:131`) | `when: enable_mariadb or enable_external_mariadb_load_balancer` |
| `Apply role mariadb` | `ansible/site.yml:471-479` | `mariadb` + `&enable_mariadb_True` | `mariadb` | **none** | `gather_facts: false` (facts come from `gather-facts.yml`, `site.yml:2`) |
| `Recover mariadb` | `ansible/mariadb_recovery.yml:1-9` | `mariadb` (no `enable_` intersection) | `mariadb` | none | play var `mariadb_recover: true`. Uses implicit `gather_facts` (default on, ansible 2.9.27 `lib/ansible/executor/play_iterator.py:285-288`). CLI passes `kolla_action=deploy` and `common_run=true` (`tools/kolla-ansible:368-372`) |
| `Backup MariaDB` | `ansible/mariadb_backup.yml:1-7` | `mariadb` | `mariadb` | none | role `when: enable_mariabackup`. CLI passes `kolla_action=backup`, `mariadb_backup_type=full/incremental` and `common_run=true` (`tools/kolla-ansible:373-376`) |

**What it means that there is no `serial:` line (FACT plus reasoning):**
- `ANSIBLE_SERIAL`/`kolla_serial` is **ignored** for MariaDB on `reconfigure` and `upgrade`. All mariadb hosts are
  always in one batch.
- This is required by the design. `lookup_cluster.yml` uses `group_by` and `groups.mariadb_*` across the whole cluster
  in one pass (port liveness, WSREP state, volume existence) to decide bootstrap, fail-fast and restart batches
  (`ansible/roles/mariadb/tasks/lookup_cluster.yml:10-77`). Under serial these groups would only describe the current
  batch.
- Rolling behaviour comes from the **handlers** (modulo-4 batching, see 1.5), not from Ansible `serial`.
- `--limit` still narrows the play: Ansible applies the limit when it resolves the play's hosts (ansible 2.9.27
  `lib/ansible/executor/playbook_executor.py:257`, `lib/ansible/inventory/manager.py:364-365,380-383`), and a `group_by`
  group only receives the hosts that ran the task (`lib/ansible/plugins/action/group_by.py:49`,
  `lib/ansible/plugins/strategy/__init__.py:667-669,846-889`). Group-derived decisions then only see the limited hosts
  (for example `mariadb_cluster_exists` is computed from `groups.mariadb_had_volume_True` among play hosts). The
  "existing but stopped" check uses the full inventory length `groups['mariadb'] | length > 1`
  (`lookup_cluster.yml:38-42`). FACT from these lines: `--limit` to a single new node on an existing cluster makes that
  node treat the cluster as new (`mariadb_cluster_exists=false`, `lookup_cluster.yml:10-17`), so it waits for WSREP
  Synced with only a 60 s budget (`restart_services.yml:28-46`).

### 1.2 `mariadb_services` (`ansible/roles/mariadb/defaults/main.yml:2-47`)

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `mariadb` | `mariadb` | `mariadb` | `true` | Volumes: `/etc/kolla/mariadb`, named volume `mariadb:/var/lib/mysql`, `kolla_logs` (`:77-82`). No `environment`. HAProxy `mariadb` (internal, enabled unless external LB): `mode tcp`, client/server timeouts 3600 s, `option httpchk` when clustercheck is enabled, else `mysql-check user haproxy post-41` (`:10-23`). `custom_member_list` = `internal_haproxy_members`, where **only the first host is active and every other host is `backup`**: `{% if not loop.first %} backup{% endif %}`, `check port 4569 inter 2000 rise 2 fall 5` (`:58`). HAProxy `mariadb_external_lb` uses inventory hostnames as addresses (`:24-35,59`) |
| `mariadb-clustercheck` | `mariadb_clustercheck` | `mariadb` | `enable_mariadb_clustercheck` (defaults to `enable_haproxy`, `:118`) | env `MYSQL_USERNAME=haproxy`, `MYSQL_PASSWORD=""`, `AVAILABLE_WHEN_DONOR=1` (`:43-47`). xinetd on `mariadb_clustercheck_port` 4569 (`templates/xinetd-clustercheck.j2:9`) |

Other defaults: `database_max_timeout: 120` (`:53`); `mariadb_service: "{{ mariadb_services['mariadb'] }}"` is used by
the recovery and WSREP checks (`:95`); `mariadb_backup_host: "{{ groups['mariadb'][0] }}"` (`:109`); backup user
`backup`, schema `PERCONA_SCHEMA` (`:110-111`). Ports: 3306, wsrep 4567, IST 4568, SST 4444, clustercheck 4569
(`ansible/group_vars/all.yml:366-370`). `enable_mariabackup: "no"` (`group_vars/all.yml:661`).

### 1.3 Task flow per `kolla_action`

| Action | Task files (in order) | Key behaviour |
|---|---|---|
| **deploy** | `deploy.yml`: `config.yml` -> `check-containers.yml` -> `bootstrap.yml` (= `lookup_cluster.yml` -> `bootstrap_cluster.yml` [only if no cluster and host is `groups['mariadb'][0]`] -> `recover_cluster.yml` [only if `mariadb_recover`]) -> `meta: flush_handlers` -> `register.yml` -> `check.yml` | `ansible/roles/mariadb/tasks/deploy.yml:1-14`, `bootstrap.yml:1-10` |
| **reconfigure** | `import_tasks: deploy.yml` (identical to deploy) | `tasks/reconfigure.yml:2` |
| **upgrade** | `deploy.yml`, then **"Run upgrade in MariaDB container"** (`upgrade_mariadb`, `KOLLA_UPGRADE`, `DB_HOST=api_interface_address`, `detach: False`) on **every** mariadb host, with no `run_once` and no image-changed condition | `tasks/upgrade.yml:1-26` |
| **deploy-containers** | `check-containers.yml` -> `lookup_cluster.yml` (prerequisite for the handlers; comment `# handlers prerequisite`). Handlers run at end of play | `tasks/deploy-containers.yml:1-5` |
| **pull** | `service-images-pull` (pulls `mariadb` and `mariadb-clustercheck` if enabled) | `tasks/pull.yml`, `ansible/roles/service-images-pull/tasks/main.yml:1-16` |
| **stop** | `service-stop`: `stop_container` for each enabled, mapped service **on all hosts at once**, unless the name is in `skip_stop_containers` | `tasks/stop.yml`, `ansible/roles/service-stop/tasks/main.yml:1-12` |
| **precheck** | `service-precheck` (inventory group exists) plus free-port checks for 3306/4567/4568/4444, only if no `mariadb` container is running | `tasks/precheck.yml:1-53` |
| **check** | `check.yml`: from **every** host, `docker exec mariadb mysql -h <VIP> -P 3306 -u haproxy -e 'show databases;'`, 6 retries x 10 s | `tasks/check.yml:1-9` |
| **config** (genconfig) | `config.yml` (handlers guarded by `kolla_action != "config"`) | `handlers/main.yml:72,86,109` |
| **backup** | `backup.yml`: one-shot `mariabackup` container (`detach: False`, `remove_on_exit: True`) on `mariadb_backup_host` only, mounting `mariadb:/var/lib/mysql` and `mariadb_backup:/backup` and running `kolla_set_configs && /usr/local/bin/kolla_mariadb_backup.sh` with `BACKUP_TYPE` | `tasks/backup.yml:1-22` |
| **recovery** (`mariadb_recovery`) | `kolla_action=deploy` with `mariadb_recover=true`, so the full deploy path runs, and `bootstrap.yml` includes `recover_cluster.yml`. The port and WSREP block of `lookup_cluster.yml` is **skipped** (`when: not mariadb_recover`) | `lookup_cluster.yml:78`, `bootstrap.yml:9-10` |

#### `lookup_cluster.yml` (runs on deploy, reconfigure, upgrade and deploy-containers)

1. `create_volume mariadb`. If the volume already existed (not changed), the host joins group `mariadb_had_volume_True`
   (`:2-13`).
2. `mariadb_cluster_exists = groups.mariadb_had_volume_True is defined` (`:15-17`).
3. Unless recovering: `wait_for` port 3306 with `search_regex: MariaDB`, `timeout: 10`, `ignore_errors`, then
   `group_by mariadb_port_alive_{True,False}` (`:20-33`).
4. **Fail fast** with "MariaDB cluster exists but is stopped. Please start it using kolla-ansible mariadb_recovery" if
   there is more than one node, the cluster exists and no node is alive (`:35-42`).
5. On alive nodes, `SHOW STATUS LIKE "wsrep_local_state_comment"`, then `group_by mariadb_sync_status_<state>`
   (`:44-69`).
6. **Fail fast** with "MariaDB cluster is not synced" unless *every* alive node is `Synced` (`:71-77`). So a reconfigure
   refuses to run while any node is Donor or Joining.

#### First bootstrap (`bootstrap_cluster.yml`)

- On `groups['mariadb'][0]` only, when no host had a volume: run `bootstrap_mariadb` (`KOLLA_BOOTSTRAP`,
  `DB_ROOT_PASSWORD`, `DB_MAX_TIMEOUT`), `detach: False`, notify **`Bootstrap MariaDB cluster`**, and
  `set_fact bootstrap_host` (`tasks/bootstrap_cluster.yml:1-27`).

#### Recovery (`recover_cluster.yml`), in order

1. Fail if no cluster volume exists ("Cheching for mariadb cluster", typo in the original) (`:2-5`).
2. Delete `/tmp/kolla_mariadb_grastate.dat` on the hosts and `/tmp/kolla_mariadb_recover_inventory_name` on the
   **controller** (`delegate_to: localhost`, `run_once`) (`:7-21`).
3. The following block is skipped if `mariadb_recover_inventory_name` is supplied with `-e`, which lets the operator
   force the bootstrap host (`:97-98`):
   - **Stop the `mariadb` container on every host** (`:24-29`). This happens even if some nodes are healthy, so running
     recovery on a partially-up cluster causes a full DB outage.
   - Run `mariadb_wsrep_recovery` with `BOOTSTRAP_ARGS=--wsrep-recover`, `detach: false` (`:33-47`).
   - Copy `<docker_runtime_directory or /var/lib/docker>/volumes/kolla_logs/_data/mariadb/mariadb.log` to `/tmp`, then
     parse `tail -n 200 ... Recovered position` to get the seqno (`:49-58`). `seqno = stdout_lines[0]` (`:68-71`). NOT
     AVAILABLE: whether an empty parse makes that host fail (index error) and so drops it from the play.
   - Each host compares its seqno against every other host, using a bash regex guard. A host with **no larger peer**
     writes its own name to the controller temp file (`:73-92`). On a tie, every tied host writes and the last writer
     wins (harmless when the seqnos are equal).
   - Every host reads the chosen name with `lookup('file', ...)` (`:94-96`).
4. `bootstrap_host = mariadb_recover_inventory_name` (`:100-102`). On that host,
   `lineinfile grastate.dat safe_to_bootstrap: 1`, editing the Docker volume path on the host directly (`:104-113`).
5. On the bootstrap host: start a `mariadb` container with `BOOTSTRAP_ARGS: --wsrep-new-cluster`, label `BOOTSTRAP` and
   `restart_policy: no` -> wait for the port -> `SET GLOBAL wsrep_provider_options='pc.bootstrap=yes'` -> wait for
   `wsrep_evs_state` to report `OPERATIONAL` (10 x 6 s) (`:115-171`).
6. **"Restart slave MariaDB container(s)"**: `start_container` loops over `with_dict: mariadb_services` on all other
   hosts **at once**, then waits only for the **port**, not for WSREP Synced (`:173-201`).
7. **"Restart master MariaDB container(s)"**: `recreate_or_restart_container` on the bootstrap host (drops the bootstrap
   args and label), then waits for the port (`:203-231`). Finally `wait_for_loadbalancer.yml` (`:233`).
8. Handlers notified earlier by config/check-containers do nothing, because they require the `mariadb_port_alive_*`
   groups and those were never created in recovery mode (`handlers/main.yml:68-71,83-85`).

### 1.4 Config files generated (`ansible/roles/mariadb/tasks/config.yml`)

| Destination (`/etc/kolla/...`) | Source / merge order | Notifies | Lines |
|---|---|---|---|
| `mariadb/`, `mariadb-clustercheck/` dirs | (directory) | none | `:2-13` |
| `mariabackup/` dir | only if `enable_mariabackup` and the host is `mariadb_backup_host` | none | `:15-25` |
| `mariabackup/my.cnf` | `merge_configs`: `templates/backup.my.cnf.j2` + `/etc/kolla/config/backup.my.cnf` + `/etc/kolla/config/mariadb/<host>/backup.my.cnf`. The template contains backup user/password and `host={{ database_address }}` (**VIP**) | **none** | `:27-40`; `templates/backup.my.cnf.j2:1-6` |
| `<svc>/config.json` (both services) | `templates/{mariadb,mariadb-clustercheck}.json.j2`. `mariadb.json.j2` recursively chowns `/var/log/kolla/mariadb` and `/var/lib/mysql` on every `COPY_ALWAYS` start, the bootstrap, upgrade and `--wsrep-recover` one-shots included (`templates/mariadb.json.j2:18-29`; [Kolla images §5.4](../../concepts/kolla-images.md#54-mariadb-what-the-image-does-not-do)) | `restart <svc>` (`restart mariadb` / `restart mariadb-clustercheck`) | `:42-53` |
| `mariabackup/config.json` | `templates/mariabackup.json.j2` | none | `:55-65` |
| `mariadb/galera.cnf` | `merge_configs`: `templates/galera.cnf.j2` + `/etc/kolla/config/galera.cnf` + `/etc/kolla/config/mariadb/<host>/galera.cnf` | `restart mariadb` | `:67-83` |
| `<svc>/wsrep-notify.sh` | `templates/wsrep-notify.sh.j2`. The loop runs over **both** services, so it is also written into the clustercheck directory | `restart mariadb` | `:85-96` |
| `mariadb-clustercheck/clustercheck` | `templates/xinetd-clustercheck.j2` | `restart mariadb-clustercheck` | `:98-111` |

Notable `galera.cnf.j2` contents:
- `wsrep_cluster_address=gcomm://` lists **all** `groups['mariadb']` hosts when there are two or more, and is empty on a
  single node (`:29`). Adding or removing a DB node therefore changes galera.cnf on every node, which triggers a rolling
  restart of the whole cluster.
- `innodb_buffer_pool_size` is 40 % of `ansible_facts.memtotal_mb`, capped at 8192M (`:63-68`). The file depends on
  facts, so a RAM change causes a restart.
- `wsrep_sst_method=mariabackup` and `wsrep_sst_auth={{ database_user }}:{{ database_password }}` (root credentials)
  (`:2,52-53`); `max_connections=10000` (`:58`); `wsrep_notify_cmd=/usr/local/bin/wsrep-notify.sh` (`:55`).
- `wsrep-notify.sh.j2` renames the `haproxy` MySQL user to `haproxy_blocked` locally (`SET SESSION wsrep_on=off`)
  whenever the node is not Synced (or is a non-mariabackup Donor). The `mysql-check` HAProxy mode then marks the node
  down (`templates/wsrep-notify.sh.j2:10-11,53-77`).

### 1.5 Handlers (`ansible/roles/mariadb/handlers/main.yml`), in definition order

| # | Name | listen | Action / logic | Lines |
|---|---|---|---|---|
| 1 | Starting first MariaDB container | `Bootstrap MariaDB cluster` | `start_container mariadb` with `BOOTSTRAP_ARGS: --wsrep-new-cluster`, label `BOOTSTRAP`, `restart_policy: no` | `:2-20` |
| 2 | Wait for first MariaDB service port liveness | `Bootstrap MariaDB cluster` | `wait_for` 3306 `search_regex MariaDB`, retries 10, delay 6 | `:23-34` |
| 3 | Wait for first MariaDB service to sync WSREP | `Bootstrap MariaDB cluster` | wait until `wsrep_local_state_comment == Synced`, 10 x 6 s | `:36-49` |
| 4 | Creating haproxy mysql user | `Bootstrap MariaDB cluster` | `kolla_toolbox mysql_user haproxy`, password `""`, host `%`, `USAGE` | `:51-64` |
| 5 | **Restart MariaDB on existing cluster members** | `restart mariadb` | `include_tasks restart_services.yml` with `loop: [0,1,2,3]` and `when: inventory_hostname in groups.mariadb_port_alive_True and groups.mariadb_port_alive_True.index(inventory_hostname) % 4 == item` | `:66-78` |
| 6 | Start MariaDB on new nodes | `restart mariadb` | `include_tasks restart_services.yml` for hosts in `mariadb_port_alive_False` that are not `bootstrap_host`. **All at once** | `:80-87` |
| 7 | Ensure MariaDB is running normally on bootstrap host | `Bootstrap MariaDB cluster` | `include_tasks restart_services.yml`. Recreates the bootstrap container as a normal one (the `BOOTSTRAP` label differs) | `:89-91` |
| 8 | Restart mariadb-clustercheck container | `restart mariadb-clustercheck` | `recreate_or_restart_container` on all notified hosts **at once** | `:93-109` |

`restart_services.yml`: `recreate_or_restart_container mariadb` -> wait for port 3306 (`timeout 60`, `retries 10`,
`delay 6`) -> wait for WSREP `Synced` (**10 x 6 s = about 60 s budget**). The WSREP wait is skipped for new nodes
joining an existing cluster ("we don't want to wait for new nodes to fully sync") (`tasks/restart_services.yml:1-46`).

**Rolling semantics (FACT, from the Ansible source):** In a handler, each `(file, loop-item vars)` pair of a looped
`include_tasks` becomes a separate `IncludedFile`, and skipped items add none (ansible 2.9.27
`lib/ansible/playbook/included_file.py:51-56,80-82,92-95,175,191-209`). `_do_handler_run` processes the included files
**one after another**, each on its own hosts (`lib/ansible/plugins/strategy/__init__.py:1046-1064`; the same logic is in
ansible 2.8.20 `lib/ansible/playbook/included_file.py:50-54` and `lib/ansible/plugins/strategy/__init__.py:953-969`).
Each host runs only the item equal to its index modulo 4 in the `mariadb_port_alive_True` list
(`handlers/main.yml:66-78`). Handler 5 therefore restarts in **4 sequential waves**: the hosts at index 0,4,8,..., the
hosts at 1,5,9,..., the hosts at 2,6,... and the hosts at 3,7,.... NOT AVAILABLE: the order in which the waves run,
which follows the order in which the hosts' include results are processed (`included_file.py:66,191-201`), and whether
`mariadb_port_alive_True` follows inventory order, since `group_by` adds each host as its result is processed
(`lib/ansible/plugins/strategy/__init__.py:667-669,882-883`).
- With 4 nodes or fewer, nodes restart **strictly one at a time**, and each waits for port + Synced before the next.
- With 5 or more nodes, up to ceil(N/4) nodes restart at once (2 of 5, 2 of 8, 3 of 9). That is always fewer than half
  of the nodes, so a majority of nodes stays up while one wave restarts, but more than one node is down at the same
  time.
- **Failure mode:** if one node fails its 60 s WSREP-sync wait (for example a long IST/SST), only *that host* is marked
  failed (ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:548-561`). No play sets `any_errors_fatal` (`grep`
  finds it only in `nova.yml` and `nova-cell`), and the next included file still runs on its own hosts
  (`:1019-1020,1046-1064`), so the next wave still restarts its nodes. NOT AVAILABLE: whether the failed node is then
  still joining, whether that can leave a single Synced node acting as donor, and so how large the quorum and
  availability risk is.

**Handler order consequences (FACT):**
- *First deploy:* config/check-containers notify `restart mariadb` on every host, and the bootstrap host additionally
  gets `Bootstrap MariaDB cluster`. Order: 1-4 (bootstrap node up with `--wsrep-new-cluster` and Synced, haproxy user
  created) -> 5 skipped (no alive nodes) -> 6 starts **all other nodes at once** -> 7 restarts the bootstrap node
  normally -> 8.
- *Scale-out:* 5 rolling-restarts the existing members first (their `wsrep_cluster_address` changed), then 6 starts the
  new nodes without waiting for SST to finish.

### 1.6 Bootstrap, DB and registration; what re-runs on reconfigure

- `bootstrap_mariadb` runs **only** when no host had a `mariadb` volume and only on `groups['mariadb'][0]`
  (`bootstrap.yml:4-7`). It does not re-run on reconfigure.
- `register.yml` **runs on every deploy/reconfigure/upgrade**: `wait_for_loadbalancer` (VIP:3306, `run_once`). When
  `enable_mariabackup` is set it also creates `PERCONA_SCHEMA`, creates the `backup` user (`append_privs`, password
  re-applied) and grants on the schema (`tasks/register.yml:1-52`).
- `check.yml` runs on every deploy/reconfigure, from every host through the VIP using the passwordless `haproxy` user
  (`tasks/check.yml:1-9`).
- `lookup_cluster.yml` checks (port, WSREP, fail-fast) run on every deploy/reconfigure/upgrade/deploy-containers.
- Backup prerequisite: `my.cnf`, the backup user and the `mariabackup` config are created only by deploy/reconfigure
  with `enable_mariabackup: yes`. `kolla-ansible mariadb_backup` itself runs only `backup.yml`. A reconfigure is
  therefore required after enabling backups (`config.yml:15-65`, `register.yml`, `backup.yml`; the docs at
  `doc/source/admin/mariadb-backup-and-restore.rst` describe this step).

### 1.7 Dependencies

- **Explicit:** `common` (meta). The haproxy play must have configured the `mariadb` frontend, which uses
  `haproxy-config` (`tasks/loadbalancer.yml:1-7`).
- **Implicit:**
  - The **VIP (haproxy + keepalived) must be up**. `register.yml` (`wait_for_loadbalancer`) and `check.yml` connect to
    `database_address` = `kolla_internal_fqdn` (`group_vars/all.yml:105`), so deploying MariaDB fails without the LB.
  - `kolla_toolbox` (from `common`) for the `mysql_user`/`mysql_db` modules.
  - Facts: `hostname` (HAProxy server names, `wsrep_node_name`) and `memtotal_mb`.
- **Consumers:** 40 roles create their DB with `kolla_toolbox mysql_db` against the VIP
  (`grep -l "module_name: mysql_db" ansible/roles/*/tasks/*.yml`). Writes go to a single active backend,
  `groups['mariadb'][0]`, because every other server is `backup` in HAProxy (`defaults/main.yml:58`).

### 1.8 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a galera.cnf change.** Every node is notified, and the restart is rolling (1 node at a time for 4
   nodes or fewer, about N/4 at a time beyond that). Each node waits for the port and `Synced` before the next.
   `groups['mariadb'][0]` is the **only active HAProxy backend** and is restarted in one of the waves (which wave runs
   first is NOT AVAILABLE, see 1.5). HAProxy checks each server with `inter 2000 rise 2 fall 5`
   (`defaults/main.yml:58`). NOT AVAILABLE: how long HAProxy takes to fail over to a backup node and back, and whether
   in-flight client connections are dropped at each step.
2. **Clustercheck restart is not rolling.** Handler 8 restarts `mariadb_clustercheck` on all notified nodes at once.
   HAProxy health checks for every backend go through port 4569 (`defaults/main.yml:22,58`). NOT AVAILABLE: whether
   HAProxy marks every backend down when that restart outlasts the `fall 5` x `inter 2000` check settings, which would
   mean a short total DB outage through the VIP.
3. **WSREP-sync wait is only about 60 s** (`restart_services.yml:37-39`; handlers `:45-47`). A restart that needs IST or
   SST longer than that fails the handler, and see the failure-mode note in 1.5.
4. **Fail-fast guards.** Reconfigure aborts if the cluster is fully stopped (multi-node) or any alive node is not Synced
   (`lookup_cluster.yml:35-42,71-77`). `kolla-ansible stop` stops every node at once (`service-stop`), so **the next
   deploy/reconfigure fails** until `mariadb_recovery` is run.
5. **Recovery takes the whole cluster down.** It stops all `mariadb` containers unconditionally
   (`recover_cluster.yml:24-29`), starts all non-bootstrap nodes at once (concurrent SST/IST load on the single
   bootstrap node), and restarts the bootstrap node after the others have only opened their port. NOT AVAILABLE: whether
   restarting the bootstrap/donor node aborts a joiner's SST from it that is still running.
6. **Recovery bug:** "Restart slave/master MariaDB container(s)" loop over `with_dict: mariadb_services` with no
   `item.value.enabled` or group check (`recover_cluster.yml:183-186,213-216`). With `enable_mariadb_clustercheck: no`,
   recovery still tries to start a `mariadb_clustercheck` container: `kolla_docker` pulls the image if it is not
   present, then creates and starts the container (`ansible/library/kolla_docker.py:781-790,805-821`). If the pull
   returns an error, `kolla_docker` fails the task on that host (`:617-630`). FACT.
7. **Recovery assumptions.** It relies on `/var/lib/docker` volume paths on the host (`:51,107`), the last 200 log lines
   (`:57`), and a fixed temp file on the controller (`:88`), so concurrent recoveries from one controller would collide.
8. **Upgrade.** `mysql_upgrade` (`upgrade_mariadb`) runs on **all nodes concurrently** and on every upgrade, even when
   the image is unchanged (`upgrade.yml:4-26`). NOT AVAILABLE: whether concurrent `mysql_upgrade` on Galera nodes
   conflicts.
9. **Backup.** It runs only on `groups['mariadb'][0]` (reading that node's datadir), but `my.cnf` points the client at
   the **VIP** (`backup.my.cnf.j2:5`). NOT AVAILABLE: whether, if HAProxy has failed over away from node 0, the backup
   tool connects to a different server than the one whose files it copies. Kolla does not schedule or rotate backups
   (docs).
10. **Credentials on the command line.** Root and haproxy credentials appear in
    `docker exec ... mysql -uroot -p{{ database_password }}` command lines (`lookup_cluster.yml:47-50`,
    `restart_services.yml:30-34`, `recover_cluster.yml:150`). `no_log` hides them from Ansible output but not from the
    host process list.
11. **Scale-out restarts the whole cluster** (`wsrep_cluster_address`, `galera.cnf.j2:29`). Every time `site.yml` runs,
    `internal_haproxy_members` is also re-rendered in haproxy.

---

## 2. RabbitMQ (`ansible/roles/rabbitmq`), used twice

### 2.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial | Role params |
|---|---|---|---|---|---|
| haproxy -> `include_role rabbitmq tasks_from: loadbalancer` | `ansible/site.yml:327-334` | haproxy | `rabbitmq` | haproxy play serial | `vars: role_rabbitmq_cluster_cookie: (null), role_rabbitmq_groups: (null)`. These are blanked so the lazily templated `rabbitmq_services` does not fail. `when: enable_rabbitmq or enable_outward_rabbitmq` |
| `Apply role rabbitmq` | `ansible/site.yml:535-553` | `rabbitmq` + `&enable_rabbitmq_True` | `rabbitmq` | **none** | `role_rabbitmq_cluster_cookie: rabbitmq_cluster_cookie`, `_cluster_port: 25672`, `_epmd_port: 4369`, `_groups: rabbitmq`, `_management_port: 15672`, `_monitoring_user/_password`, `_password`, `_port: 5672`, `_user` |
| `Apply role rabbitmq (outward)` | `ansible/site.yml:555-572` | `outward-rabbitmq` + `&enable_outward_rabbitmq_True` | `rabbitmq` (**same tag**) | **none** | **`project_name: outward_rabbitmq`**, `outward_rabbitmq_cluster_cookie`, ports 5674/15674/25674/4371 (`group_vars/all.yml:422-425`), `_groups: outward-rabbitmq`, no monitoring user |

- `enable_rabbitmq` defaults to yes when either `om_rpc_transport` or `om_notify_transport` is `rabbit`
  (`group_vars/all.yml:581`). `enable_outward_rabbitmq` = `enable_murano` (`:582`).
- **Role params override role vars.** `project_name` passed as a role param beats `vars/main.yml`
  `project_name: "rabbitmq"`, because Ansible merges role params after role vars (ansible 2.9.27
  `lib/ansible/vars/manager.py:388-390,402-404`). For the outward cluster, `project_name=outward_rabbitmq` therefore
  drives the container name, the volume name, the config dir `/etc/kolla/outward_rabbitmq`, the log dir and the
  murano-specific definitions (`defaults/main.yml:4,12,16,58,61`; `templates/definitions.json.j2:3,9,15,20`).
- **What it means that there is no `serial:`:** `kolla_serial` is ignored. The full-stop upgrade (2.3) *requires* every
  node in one batch: stop the non-first nodes, then stop the first node, then restart first-node-first. Rolling restarts
  come from the handlers.
- `--tags rabbitmq` (or `--skip-tags rabbitmq`) affects **both** clusters and the haproxy fragment together.

### 2.2 `rabbitmq_services` (`ansible/roles/rabbitmq/defaults/main.yml:2-39`)

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `rabbitmq` | `{{ project_name }}` (`rabbitmq` or `outward_rabbitmq`) | `{{ role_rabbitmq_groups }}` | `true` | `environment`: `KOLLA_CONFIG_STRATEGY`, **`RABBITMQ_CLUSTER_COOKIE: role_rabbitmq_cluster_cookie`**, `RABBITMQ_LOG_DIR`. `bootstrap_environment` adds `KOLLA_BOOTSTRAP`. Volume `{{ project_name }}:/var/lib/rabbitmq/`. HAProxy: `rabbitmq_management` (http, 15672, `host_group: rabbitmq`), `rabbitmq_outward_management` (15674), and `rabbitmq_outward_external` (tcp, **external** frontend on 5674 for murano agents, 1 h timeouts). **AMQP 5672 is not load-balanced**: clients get every broker in `transport_url` |

Other defaults: `rabbitmq_pid_file: /var/lib/rabbitmq/mnesia/rabbitmq.pid` (`:71`),
`rabbitmq_server_additional_erl_args: "+S 2:2 +sbwt none ..."` (`:72`). `rabbitmq_hostname` (`:70`) is **unused**: grep
finds no reference.

**Erlang cookie:** comes from `passwords.yml` keys `rabbitmq_cluster_cookie` / `outward_rabbitmq_cluster_cookie`
(`etc/kolla/passwords.yml:227,229`). It is passed to the broker container as the env `RABBITMQ_CLUSTER_COOKIE`
(`defaults/main.yml:11,15`). The `common` role also copies `rabbitmq_cluster_cookie` (main cluster only) into
`kolla_toolbox` as `/var/lib/rabbitmq/.erlang.cookie`. A change to the host-side copy
(`{{ node_config_directory }}/kolla-toolbox/rabbitmq-erlang.cookie`) notifies `Restart kolla-toolbox container`, and
with `COPY_ALWAYS` that copy is re-copied into the container at every toolbox start
(`ansible/roles/common/tasks/config.yml:242-250`, `templates/kolla-toolbox.json.j2:4-8`). The kolla image writes
`/var/lib/rabbitmq/.erlang.cookie` **only** when `KOLLA_BOOTSTRAP` is set, then exits; a normal start only handles the
log dir (kolla `docker/rabbitmq/extend_start.sh:7-26`; see
[Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)). That
happens only in the `{{ project_name }}_bootstrap` container, which runs only when the volume was just created
(`tasks/bootstrap.yml:26`). A normal start does not touch the cookie, and the file persists in the `{{ project_name }}`
volume (`defaults/main.yml:61`). Because the cookie is in the env, `compare_container` (env compare) still picks up a
cookie change and causes a **rolling** recreate, but the recreated brokers keep their old `.erlang.cookie` file. NOT
AVAILABLE (it depends on whether `rabbitmq-server` itself reads `RABBITMQ_CLUSTER_COOKIE`, which is not in these
sources): whether a partition occurs during the roll, or whether the change is instead silently not applied to existing
brokers while `kolla_toolbox` (rabbitmqctl, used by `service-rabbitmq`) and any broker bootstrapped later on a fresh
volume get the new cookie and cannot talk to the existing nodes.

### 2.3 Task flow per `kolla_action`

| Action | Flow | Evidence |
|---|---|---|
| **deploy** | `config.yml` -> `check-containers.yml` -> `bootstrap.yml` -> `flush_handlers` | `tasks/deploy.yml:1-9` |
| **reconfigure** | = deploy | `tasks/reconfigure.yml:2` |
| **bootstrap.yml** | `create_volume {{ project_name }}`. **Only when the volume was just created** on that host: run `{{ project_name }}_bootstrap` with `bootstrap_environment`, `detach: False` | `tasks/bootstrap.yml:1-26` |
| **upgrade** | `compare_image` (registers `rabbitmq_differs`) -> `config.yml` -> `check-containers.yml` -> **stop every non-first node** (if its image differs) -> **stop the first node** -> `flush_handlers` (restart first, then the others one by one). There is no bootstrap step | `tasks/upgrade.yml:1-44` (comment `:2-4`: "full stop upgrade ... necessary when moving between major releases") |
| **deploy-containers** | `check-containers.yml` only. Handlers run at end of play | `tasks/deploy-containers.yml` |
| **pull** | `service-images-pull` | `tasks/pull.yml` |
| **stop** | `service-stop`: all nodes **at once** | `tasks/stop.yml` |
| **precheck** | group check, free ports for both clusters, and `getent ahostsv4/6 <hostname>` for every rabbit host, failing unless every line resolves to that host's api IP (nodename `rabbit@<hostname>`) | `tasks/precheck.yml:1-139` |
| **check** | **empty file** (no post-deploy check) | `tasks/check.yml:1` |
| **config** | `config.yml`. Handlers are guarded by `kolla_action != "config"` | `handlers/main.yml:12,22` |

### 2.4 Config files (`ansible/roles/rabbitmq/tasks/config.yml`)

All files go into `/etc/kolla/{{ project_name }}/`. Except `config.json`, each file uses **`with_first_found`**, which
means a **full replacement** of the template, not a merge:
`/etc/kolla/config/rabbitmq/<inventory_hostname>/<file>` -> `/etc/kolla/config/rabbitmq/<file>` -> the role template.
All of them notify **`Restart rabbitmq container`**.

| File | Template highlights | Lines |
|---|---|---|
| `config.json` | `rabbitmq.json.j2`: `/usr/sbin/rabbitmq-server`. Copies the 5 files and, on every `COPY_ALWAYS` start, recursively chowns `/var/lib/rabbitmq` (the `{{ project_name }}` volume, mnesia included) and `/var/log/kolla/{{ project_name }}`, one `chown` per directory and file (`templates/rabbitmq.json.j2:35-46`; kolla `docker/base/set_configs.py:378-385,391-393`) | `config.yml:15-26` |
| `rabbitmq-env.conf` | `RABBITMQ_NODENAME=rabbit@<hostname>`, `RABBITMQ_DIST_PORT=role_rabbitmq_cluster_port`, `ERL_EPMD_ADDRESS=api ip`, `ERL_EPMD_PORT=role_rabbitmq_epmd_port` | `config.yml:28-44`; `templates/rabbitmq-env.conf.j2:1-10` |
| `rabbitmq.conf` | `listeners.tcp.1 = api_ip:role_rabbitmq_port`; **`cluster_partition_handling = pause_minority`**; `management.load_definitions = /etc/rabbitmq/definitions.json`; `cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config` with every host in `groups[role_rabbitmq_groups]` | `config.yml:47-63`; `templates/rabbitmq.conf.j2:3-14` |
| `erl_inetrc` | `{inet6,true}` for IPv6 | `config.yml:65-81` |
| `advanced.config` | `inet_dist_use_interface` and `inet_dist_listen_min/max = role_rabbitmq_cluster_port` | `config.yml:83-99`; `templates/advanced.config.j2` |
| `definitions.json` | vhost `/` (plus the murano agent vhost for outward); user `role_rabbitmq_user` (administrator) plus an optional monitoring user (plus the murano agent user for outward); **policy `ha-all` `{"ha-mode":"all"}` on pattern `.*`**, which mirrors every queue on every node | `config.yml:101-117`; `templates/definitions.json.j2:1-24` |

**Oddity:** the override paths are hard-coded to `/etc/kolla/config/rabbitmq/...` and do **not** include
`{{ project_name }}`. A custom `rabbitmq.conf` placed there replaces the template for **both** `rabbitmq` and
`outward_rabbitmq`, including the listener and management ports. NOT AVAILABLE: whether the two brokers on one host
would then try to bind the same ports (`config.yml:37-38,56-57,...`).

### 2.5 Handlers (`ansible/roles/rabbitmq/handlers/main.yml`), in definition order

| # | Name | listen | Logic | Lines |
|---|---|---|---|---|
| 1 | Restart first rabbitmq container | `Restart rabbitmq container` | `include_tasks restart_services.yml` only on `groups[service.group] \| first` | `:6-14` |
| 2 | Restart remaining rabbitmq containers | `Restart rabbitmq container` | `include_tasks restart_services.yml`, `loop: groups[service.group]`, `when: inventory_hostname == item and not first` | `:16-26` |

`restart_services.yml`: `recreate_or_restart_container` (with env) ->
`docker exec <c> rabbitmqctl wait /var/lib/rabbitmq/mnesia/rabbitmq.pid`. There is no timeout, no retries, and **no
cluster-membership, partition or mirror-sync check** (`tasks/restart_services.yml:1-21`).

**Rolling semantics (FACT, from the Ansible source):** handler 1 runs before handler 2 (definition order, see section
0). In handler 2 each host runs only the loop item equal to its own name, so each loop item becomes its own included
file, and the included files run one after another (ansible 2.9.27
`lib/ansible/playbook/included_file.py:80-82,92-95,191-209`, `lib/ansible/plugins/strategy/__init__.py:1046-1064`). The
restart order is therefore the first node, then each remaining node **one at a time**. Restart time grows linearly with
N. Only notified hosts restart (`strategy/__init__.py:1019-1029`). NOT AVAILABLE: whether the remaining nodes restart in
inventory order; the included files are ordered by the order in which the hosts' results are processed
(`included_file.py:66,191-201`).

### 2.6 Bootstrap and registration

- The cluster/user bootstrap is declarative. Users, vhosts and policies come only from `definitions.json`, which is
  loaded at node boot (`rabbitmq.conf.j2:9`). There is no `rabbitmqctl` or `rabbitmq_user` task in the role, so a
  **changed `rabbitmq_password` takes effect only through a restart** (rolling, via the handler).
- The `{{ project_name }}_bootstrap` container runs only on hosts whose volume is newly created (`bootstrap.yml:26`). It
  does not re-run on reconfigure.
- Per-service users and vhosts are created only by the `service-rabbitmq` role
  (`ansible/roles/service-rabbitmq/tasks/main.yml:1-44`, `update_password: always`), which in Ussuri is used only by
  `nova-cell` (`ansible/roles/nova-cell/tasks/rabbitmq.yml:5,15`). Every other service shares the `openstack` user on
  vhost `/` (`group_vars/all.yml:199-216`).

### 2.7 Dependencies

- **Explicit:** `common`.
- **Implicit:**
  - Hostnames must resolve to the api IP on every node (precheck), because nodenames are `rabbit@<hostname>`.
  - Facts (`hostname`).
  - HAProxy, only for the management UI and the outward external port.
- **Consumers:** 36 roles render `transport_url` from `rpc_transport_url` / `notify_transport_url`, which list **every**
  host in `groups['rabbitmq']` (`group_vars/all.yml:206,216`; `grep -l transport_url ansible/roles/*/templates/*` -> 36
  roles). Keystone is one of them (`keystone.conf.j2:4,54`).

### 2.8 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a config change** restarts the first node first, then one node at a time. At most one node is down
   at a time, so a 3-node cluster keeps 2/3 and stays above the `pause_minority` threshold. However, the handler only
   runs `rabbitmqctl wait` and has no mirror-sync check (`restart_services.yml:1-21`). NOT AVAILABLE: whether, with
   `ha-mode: all` and the default manual sync, the next node may be stopped while mirrors on the freshly restarted node
   are still unsynchronised, which would risk message loss or unavailable queues.
2. **Upgrade = full outage of the message bus** whenever the image differs (`upgrade.yml:5-41`). Every non-first node is
   stopped, then the first node is stopped, then they restart sequentially. Any `kolla-ansible upgrade` that changes the
   rabbitmq image tag takes all RPC down for the duration of the sequential restart.
3. **Uncontrolled full stop** (`kolla-ansible stop`, power loss) followed by deploy: the handlers start the *first* node
   first and block on `rabbitmqctl wait`. NOT AVAILABLE (RabbitMQ semantics): whether, if that node was not the last to
   stop, it waits for its peers' Mnesia tables (by default about 5 min) before giving up, so that the sequential handler
   stalls or fails on node 1 before nodes 2 and 3 are started.
4. **Scaling the rabbitmq group changes `transport_url` in about 36 services**, so it restarts almost every OpenStack
   service cloud-wide when those plays run. It also changes `rabbitmq.conf` (classic_config node list) on every broker,
   which causes a rolling restart.
5. **Password change.** `definitions.json` changes cause a rolling broker restart in the rabbitmq play. Consumers get
   the new password only when their own plays run later in `site.yml`. NOT AVAILABLE: whether there is an auth-failure
   window in between.
6. **Bug (FACT): `kolla-ansible pull` with outward rabbitmq enabled.** `service-images-pull` looks up
   `lookup('vars', (kolla_role_name | default(project_name)) + '_services')` = `outward_rabbitmq_services`, and that
   variable is not defined anywhere (`ansible/roles/service-images-pull/tasks/main.yml:14`;
   `grep outward_rabbitmq_services` finds nothing). The `vars` lookup raises an undefined-variable error for a name it
   cannot find when no default is given, and the task executor turns that error into a failed result, so "Pull images"
   fails on the outward-rabbitmq hosts (ansible 2.9.27 `lib/ansible/plugins/lookup/vars.py:80-94`,
   `lib/ansible/template/__init__.py:771-773,912-914`, `lib/ansible/executor/task_executor.py:103-109,566-568,179-180`).
7. `check.yml` is empty, and `rabbitmq_hostname` is dead code.
8. The precheck runs `getent` for every rabbit host on every rabbit host, so it does N² lookups.

---

## 3. Keystone (`ansible/roles/keystone`)

### 3.1 Plays, hosts, tags, serial

| Play | Lines | Hosts | Tags | Serial |
|---|---|---|---|---|
| haproxy -> `include_role keystone tasks_from: loadbalancer` | `ansible/site.yml:229-233` | haproxy | `keystone` | haproxy serial |
| `Apply role keystone` | `ansible/site.yml:596-605` | `keystone` + `&enable_keystone_True` | `keystone` | **`serial: '{{ kolla_serial\|default("0") }}'`** (`:601`) |

What serial means here:
- With the default (`ANSIBLE_SERIAL` unset, so 0 = all hosts), every keystone node is handled in **one batch** (ansible
  2.9.27 `lib/ansible/executor/playbook_executor.py:276-278`), and handlers restart **all keystone containers at once**
  (section 0, "Handler order").
- With `ANSIBLE_SERIAL=n`, `run_once` tasks run **once per batch**: bootstrap container (db_sync), key distribution,
  register, sanity check. Each batch is a separate run on the inventory restricted to that batch, and `run_once` sends a
  task only to the first host left (`playbook_executor.py:161-169`,
  `lib/ansible/plugins/strategy/linear.py:288,315-316`).
- Fernet bootstrap is blocked when not all hosts are in the batch (3.6).
- On upgrade, `Init` (expand/migrate) runs in the batch containing `groups['keystone'][0]` and `Finish` (contract) runs
  in the batch containing `groups['keystone'][-1]`.

### 3.2 `keystone_services` (`ansible/roles/keystone/defaults/main.yml:2-55`)

| Key | container_name | group | enabled | Notable |
|---|---|---|---|---|
| `keystone` | `keystone` | `keystone` | `true` | Apache + mod_wsgi. Volumes include **`keystone_fernet_tokens:/etc/keystone/fernet-keys`** when the provider is fernet (`:95-101`). HAProxy `keystone_internal` (5000), `keystone_external` (5000, external), `keystone_admin` (35357) |
| `keystone-ssh` | `keystone_ssh` | `keystone` | `keystone_token_provider == 'fernet'` | `sshd -D` on `api_interface_address:8023` (`templates/sshd_config.j2`, `group_vars/all.yml:356`). Shares the `keystone_fernet_tokens` volume |
| `keystone-fernet` | `keystone_fernet` | `keystone` | `keystone_token_provider == 'fernet'` | Runs `crond -s -n` / `cron -f` with the rotation crontab. Shares the `keystone_fernet_tokens` volume |

Relevant globals (`ansible/group_vars/all.yml`):

| Variable | Value | Line |
|---|---|---|
| `keystone_token_provider` | `fernet` | `:836` |
| `fernet_token_expiry` | 86400 | `:838` |
| `fernet_token_allow_expired_window` | 172800 | `:840` |
| `fernet_key_rotation_interval` | expiry + window = 259200 s (3 days) | `:845` |
| `keystone_admin_url` | `admin_protocol://<internal VIP>:35357` | `:822` |
| `openstack_auth.auth_url` | `keystone_admin_url` | `:851-857` |
| `multiple_regions_names` | `[openstack_region_name]` | `:547-548` |
| `kolla_enable_sanity_checks` | `"no"` | `:56` |

### 3.3 Task flow per `kolla_action`

| Action | Flow | Evidence |
|---|---|---|
| **deploy** | `config.yml` -> `check-containers.yml` -> `clone.yml` (dev mode only) -> `bootstrap.yml` -> `flush_handlers` -> `distribute_fernet.yml` (fernet only) -> `register.yml` -> `check.yml` | `tasks/deploy.yml:1-21` |
| **reconfigure** | = deploy, so **bootstrap, distribution and registration all re-run** | `tasks/reconfigure.yml:2` |
| **upgrade** | `config.yml` -> `check-containers.yml` -> set `log_bin_trust_function_creators=1` (`run_once`, on `groups['keystone'][0]`) -> notify `Init keystone database upgrade` on `[0]` -> notify `Finish keystone database upgrade` on `[-1]` -> `flush_handlers` -> set `log_bin_trust_function_creators=0` (`run_once`, every batch). **No** bootstrap, key distribution or register | `tasks/upgrade.yml:1-48` |
| **deploy-containers** | `check-containers.yml` | `tasks/deploy-containers.yml` |
| **pull / stop** | `service-images-pull` / `service-stop` (all 3 containers, all hosts at once) | `tasks/pull.yml`, `tasks/stop.yml` |
| **precheck** | group check; free ports 35357, 5000, 8023; **assert `fernet_token_expiry` is an int between 0 and 604800** | `tasks/precheck.yml:1-71` |
| **check** | `os_auth` sanity check on `groups['keystone'][0]`, only if `kolla_enable_sanity_keystone` (default `no`) | `tasks/check.yml:1-12` |
| **config** | `config.yml`. Handlers are guarded by `kolla_action != "config"` | `handlers/main.yml:41-42,56-57,71-72` |

`bootstrap.yml` and `bootstrap_service.yml` (run on **every deploy/reconfigure**):
1. `mysql_db keystone` and `mysql_user keystone` with `keystone_database_password`, `append_privs` (`run_once`,
   `delegate_to: groups['keystone'][0]`) (`tasks/bootstrap.yml:1-34`). This re-asserts the DB user password on each run.
2. `kolla_container_facts keystone_fernet` (lists *running* containers only,
   `ansible/library/kolla_container_facts.py:72`) -> `group_by keystone_fernet_<State|bootstrap>`
   (`tasks/bootstrap_service.yml:2-17`).
3. Fail if no host has `keystone_fernet` running and not every keystone host is in `ansible_play_batch` ("Please run
   without --limit or --serial") (`:21-30`).
4. **`bootstrap_keystone` container** (`KOLLA_BOOTSTRAP`). In the kolla image, `kolla_start` sources
   `kolla_extend_start`, which sees `KOLLA_BOOTSTRAP`, runs `sudo -H -u keystone keystone-manage db_sync` and exits 0
   without starting httpd (kolla `docker/base/start.sh:15-18`, `docker/keystone/keystone/extend_start.sh:41-46`; see
   [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)).
   `EXTRA_KEYSTONE_MANAGE_ARGS` is empty by default (kolla `extend_start.sh:21`) and kolla-ansible does not set it. It
   is `run_once` without `delegate_to` (first host of the batch) and runs **on every deploy/reconfigure**
   (`bootstrap_service.yml:32-49`).
5. `bootstrap_keystone_fernet`: `keystone-manage fernet_setup`, `run_once`, `delegate_to: groups['keystone'][0]`, **only
   if no `keystone_fernet` container is running on any play host** (`:51-75`).

`distribute_fernet.yml` (every deploy/reconfigure):
- Wait for port 8023 on every host (`:2-10`).
- **`docker exec keystone_fernet /usr/bin/fernet-push.sh`**, `run_once`, `delegate_to` = the first host in
  `keystone_fernet_running` (or `groups['keystone'][0]` on first bootstrap) (`:12-19`).

`register.yml` (every deploy/reconfigure):
- `docker exec keystone kolla_keystone_bootstrap <admin user> <admin pw> <project> admin <admin_url> <internal_url> <public_url> <region>`, once per region (`run_once`) (`tasks/register.yml:2-12`).
- `service-ks-register` for the identity service and its 3 endpoints (`:14-19`).
- `os_keystone_role _member_` (`:21-31`).

### 3.4 Config files (`ansible/roles/keystone/tasks/config.yml`)

| Destination (`/etc/kolla/...`) | Source / merge order | Notifies | Lines |
|---|---|---|---|
| `<svc>/config.json` | `keystone.json.j2` / `keystone-ssh.json.j2` / `keystone-fernet.json.j2` | `Restart <svc> container` | `:45-56` |
| `keystone/keystone.conf`, `keystone-fernet/keystone.conf` | `merge_configs`: `templates/keystone.conf.j2` + `/etc/kolla/config/global.conf` + `/etc/kolla/config/keystone.conf` + `/etc/kolla/config/keystone/<svc>.conf` + `/etc/kolla/config/keystone/<host>/keystone.conf` | `Restart keystone container` / `Restart keystone-fernet container` | `:58-77` |
| `keystone/keystone-startup.sh` | template. Waits up to 36 x 5 s (**3 min**) for fernet key `0`, then `exec httpd/apache2` | `Restart keystone container` | `:79-91`; `templates/keystone-startup.sh.j2:9-24` |
| `keystone/domains/*` | Created only if `/etc/kolla/config/keystone/domains` exists on the controller. Every file in it is **templated** (Jinja) into `/etc/kolla/keystone/domains/`. `keystone.conf` gains `[identity] domain_specific_drivers_enabled = true, domain_config_dir = /etc/keystone/domains` | `Restart keystone container`. A file added once `keystone.conf` already has the domain settings is not yet in the container and the `domains` entry is optional, so `kolla_set_configs --check` exits 2 and "Check keystone containers" fails on every keystone host before the handler runs (`templates/keystone.json.j2:24-29`, `tasks/deploy.yml:1-13`; [Kolla images §3.3](../../concepts/kolla-images.md#33-exit-codes)) | `:34-39,93-130`; `keystone.conf.j2:24-28` |
| `<keystone, keystone-fernet>/policy.{yaml,json}` | First found in `/etc/kolla/config/keystone/` (`supported_policy_format_list`) | `Restart <svc> container` | `:15-32,132-145` |
| `keystone/wsgi-keystone.conf` | `with_first_found`: `/etc/kolla/config/keystone/<host>/wsgi-keystone.conf` -> `/etc/kolla/config/keystone/wsgi-keystone.conf` -> template. `processes = openstack_service_workers` = min(vCPU, 5) (`group_vars/all.yml:550`) | `Restart keystone container` | `:147-163`; `templates/wsgi-keystone.conf.j2:41,61` |
| `keystone/keystone-paste.ini` | Only if `/etc/kolla/config/keystone/keystone-paste.ini` exists | `Restart keystone container` | `:165-189` |
| (controller) cron generator | `python fernet_rotate_cron_generator.py -t <interval_s//60> -i <index in groups['keystone']> -n <len>`, `delegate_to: localhost`, per host | none (`changed_when: false`) | `:191-206` |
| `keystone-fernet/{crontab, fernet-rotate.sh, fernet-node-sync.sh, fernet-push.sh, id_rsa, ssh_config}` | templates (`id_rsa` = `{{ keystone_ssh_key.private_key }}`) | `Restart keystone-fernet container` | `:208-228` |
| `keystone-ssh/{sshd_config, id_rsa.pub}` | templates (`id_rsa.pub` becomes `authorized_keys`) | `Restart keystone-ssh container` | `:230-245` |

`keystone.conf.j2` highlights:
- `transport_url = rpc_transport_url` (`:4`).
- `[database] connection` via the VIP, `max_retries = -1` (`:18-22`).
- `[token] expiration`, `allow_expired_window` (`:30-34`).
- `[fernet_tokens] max_active_keys = ceil((expiry + window) / rotation_interval) + 2`, which is **3** with the defaults
  (`:43-46`).
- `[cache] backend = oslo_cache.memcache_pool`, `memcache_servers` = every `groups['memcached']` host (`:48-51`).
- `[oslo_messaging_notifications]` uses driver `messagingv2` only when ceilometer or barbican topics are enabled,
  otherwise `noop` (`:53-60`; `defaults/main.yml:125-134`).

### 3.5 Handlers (`ansible/roles/keystone/handlers/main.yml`). Order is load-bearing (comment `:2-3`)

| # | Name | Logic | Lines |
|---|---|---|---|
| 1 | Init keystone database upgrade | `init_upgrade_database` container, `KOLLA_UPGRADE`, `run_once`, only when `kolla_action == upgrade` and the host is `groups['keystone'][0]` | `:5-27` |
| 2 | Restart keystone-ssh container | `recreate_or_restart_container`. All notified hosts in the batch **in parallel** | `:29-42` |
| 3 | Restart keystone-fernet container | same | `:44-57` |
| 4 | Restart keystone container | same: **no rolling, no wait for port or health** | `:59-72` |
| 5 | Finish keystone database upgrade | `finish_upgrade_database`, `KOLLA_FINISH_UPGRADE`, `run_once`, `kolla_action == upgrade`. No host guard: it relies on being notified only on `groups['keystone'][-1]` (`upgrade.yml:27-30`) | `:74-95` |

### 3.6 Fernet key lifecycle (FACT unless marked)

- **Storage:** a per-host Docker volume `keystone_fernet_tokens`, shared by the `keystone`, `keystone_fernet` and
  `keystone_ssh` containers (`defaults/main.yml:42,54,101`).
- **Initial setup:** `keystone-manage fernet_setup` on `groups['keystone'][0]` only when no `keystone_fernet` container
  is *running* anywhere in the play (`bootstrap_service.yml:51-75`). The code comment admits the detection is imprecise:
  "This does not catch some cases ... the keystone_fernet container is created but not running ... Probably what we care
  about is the existence of Fernet key 0" (`:9-13`). NOT AVAILABLE (Keystone upstream behaviour): whether `fernet_setup`
  is a no-op when key `0` already exists, which would make a re-run on a node with an intact volume harmless. On a
  **rebuilt `groups['keystone'][0]`** (empty volume), with every `keystone_fernet` container stopped (for example after
  `kolla-ansible stop`), a deploy runs `fernet_setup` on that node and then **pushes its key set with `rsync --delete`
  to every node** (`:51-75`; `distribute_fernet.yml:12-19`; `templates/fernet-push.sh.j2:6-10`). NOT AVAILABLE: whether
  `fernet_setup` then generates brand-new keys and whether that invalidates all tokens; the code comment at
  `bootstrap_service.yml:19-20` names this risk.
- **Rotation:** cron in `keystone_fernet` runs `fernet-rotate.sh` = `keystone-manage fernet_rotate` && `fernet-push.sh`
  (`templates/fernet-rotate.sh.j2:6-8`). `fernet-push.sh` runs, for each other keystone host,
  `rsync -az ... --delete /etc/keystone/fernet-keys/ keystone@<host>:/etc/keystone/fernet-keys` over ssh port 8023,
  under `set -o errexit` (`templates/fernet-push.sh.j2:3-10`).
- **Schedule:** the generator gives each host a weekly crontab (min hour * * dow) in round-robin with offset
  `interval * index` (`files/fernet_rotate_cron_generator.py:41-96`). It deliberately under-rotates across the week
  boundary (`:55-56,69`). Working through `generate()` by hand for these inputs, which all take the day branch (offset
  `interval * index`, step `interval * hosts`, a job only while `time + interval <= 10080`; `:57-58,67-75`), gives:

  | Interval | Hosts | Result |
  |---|---|---|
  | 4320 min (default 3 days) | 3 | h0 = `Sun 00:00`, h1 = `Wed 00:00`, **h2 = no jobs**. Gaps 3 d / 4 d |
  | 4320 min | 5 | only h0 and h1 have jobs |
  | 1440 min | 3 | h0 Sun/Wed/Sat, h1 Mon/Thu, h2 Tue/Fri |

  Crons run in the container's local time (`/etc/localtime` is mounted).
- **Distribution on every deploy/reconfigure:** `fernet-push.sh` runs from the first running node
  (`distribute_fernet.yml:12-19`), so that node's key set **overwrites** every other node (`--delete`).

### 3.7 Bootstrap, DB and registration: what re-runs on `reconfigure`

Re-runs every time:
- `mysql_db` and `mysql_user keystone`
- the `bootstrap_keystone` container (db_sync)
- the fernet-bootstrap check
- `fernet-push.sh`
- `kolla_keystone_bootstrap` for each region. The keystone image installs kolla
  `docker/keystone/keystone/keystone_bootstrap.sh` under that name (kolla `docker/keystone/keystone/Dockerfile.j2:10`).
  It runs `keystone-manage bootstrap` with the admin user, password, project, role, admin/internal/public URLs, service
  name `keystone` and the region (kolla `keystone_bootstrap.sh:38`), and reports unchanged only if exactly nine output
  lines match its expected 'exists'/'already has'/'skipping' messages (domain, project, user, role, role assignment,
  region, three endpoints; `:43-56`). NOT AVAILABLE (upstream `keystone-manage bootstrap` is not in these sources):
  whether it re-asserts the admin user, project, role and endpoints and **resets the admin password to
  `keystone_admin_password`** if it differs. The wrapper has no pattern for a password reset (`:43-56`), so whether such
  a reset shows as changed is also NOT AVAILABLE.
- `service-ks-register` (identity service and endpoints)
- `_member_` role
- the optional sanity check

All of these are `run_once` per batch, except the cron generator, which runs on the controller once per host.

### 3.8 Dependencies

- **Explicit:** `common`.
- **Implicit, upstream:**
  - **MariaDB** via the VIP (`keystone_database_address`, `defaults/main.yml:63`).
  - **memcached**: `[cache]` (`keystone.conf.j2:48-51`). The memcached play (`site.yml:481`) runs before keystone
    (`:596`).
  - **RabbitMQ**: `transport_url` is always rendered, and notifications go out only if ceilometer or barbican is enabled
    (`keystone.conf.j2:4,53-60`).
  - **HAProxy VIP**: `keystone_admin_url` is used by `openstack_auth` for register and check.
  - **kolla_toolbox** (`os_*` modules).
  - `passwords.yml` `keystone_ssh_key` (`etc/kolla/passwords.yml:202-204`).
- **Downstream:** see 3.10.

### 3.9 Operationally notable behaviour, risks and oddities

1. **Reconfigure with a config change** (default serial 0) restarts `keystone_ssh`, then `keystone_fernet`, then
   `keystone`, each **on all keystone hosts simultaneously** (handlers `:29-72`). The result is a brief **Keystone-wide
   API outage**. Nothing waits for the API to return before `register.yml` runs (which uses `run_once` plus
   `until`/retries inside `service-ks-register`, `ansible/roles/service-ks-register/tasks/main.yml:20-22`). NOT
   AVAILABLE: whether other services keep validating cached tokens via memcached during the restart. Set
   `ANSIBLE_SERIAL` for a rolling reconfigure.
2. **What restarts keystone indirectly.** `keystone.conf` embeds every memcached host and every rabbitmq host, and the
   fernet crontab and `fernet-push.sh` embed the keystone host list and index. Adding or removing a memcached, rabbitmq
   or keystone node therefore restarts keystone, and keystone-fernet as well for keystone node changes.
3. **Fernet push has no partial-failure handling.** `set -o errexit` stops at the first unreachable peer, so later peers
   are not updated either (`fernet-push.sh.j2:3-10`). The next scheduled rotation runs on another node (round-robin,
   3.6), which may be one of the peers left with the *stale* set. That node runs `fernet_rotate` and then
   `fernet-push.sh`, whose `rsync --delete` overwrites the key set of each peer it reaches, stopping at the first
   failure (`templates/fernet-rotate.sh.j2:6-8`, `templates/fernet-push.sh.j2:3-10`). The reconfigure-time push from
   "first running node" works the same way. NOT AVAILABLE (Keystone key handling): whether this removes the key that
   signed live tokens and so causes mass 401s.
4. **Bug in the cron generator hour calculation.** In the day branch, `hour = time % HOUR_SPAN` is computed where
   `(time % DAY_SPAN) // HOUR_SPAN` was intended (`fernet_rotate_cron_generator.py:70-72`). It is harmless when the
   interval is a whole number of days (the default). Otherwise it can **over-rotate**. Read from the code: with interval
   3600 min (60 h, i.e. `fernet_token_expiry=43200`), h1 has `time = 3600`, so `day = 2` and `hour = 3600 % 60 = 0`,
   giving `day 2 00:00` instead of `day 2 12:00` after h0's `day 0 00:00`, which is a **48 h gap with a 60 h interval**.
   NOT AVAILABLE (Keystone key handling): whether, with `max_active_keys=3`, a key can then be deleted before the
   allow-expired window of tokens it signed has elapsed.
5. **The precheck validates the wrong variable.** It asserts `fernet_token_expiry <= 604800` (`precheck.yml:52-71`, and
   its message talks about "rotate the fernet keys"). The generator, however, is fed `fernet_key_rotation_interval` (=
   expiry + 2 d by default) and fails above 10080 min (`generator:61-64`). The generator exits 0 with `{"failed": true}`
   (`:33-38,119`), so the `command` task succeeds and **`set_fact cron_jobs` then errors on a missing key**
   (`config.yml:202-206`). Any `fernet_token_expiry` above 5 days with the default window passes precheck but breaks
   deploy.
6. **Under-rotation by design.** With 3 or more hosts and the 3-day default, only 2 hosts ever rotate. Rotations happen
   at a fixed local `00:00` on Sunday and Wednesday.
7. **Shared SSH key.** Every node gets the same `keystone_ssh_key`, and `ssh_config` sets `StrictHostKeyChecking no`,
   `UserKnownHostsFile /dev/null` (`templates/ssh_config.j2:1-4`). NOT AVAILABLE: whether anyone holding the private key
   and reaching port 8023 on the API network can overwrite fernet keys as `fernet-push.sh` does
   (`templates/fernet-push.sh.j2:8`), and whether that allows token forgery.
8. **Domain config cleanup.** Removing a file from `/etc/kolla/config/keystone/domains` is never propagated: no task
   deletes stale files in `/etc/kolla/keystone/domains/`. FACT: under the default `COPY_ALWAYS` the stale file is copied
   back into the container at every start, even after a recreate: `domains` is a directory entry
   (`templates/keystone.json.j2:24-29`), so `kolla_set_configs` deletes `/etc/keystone/domains` and re-copies the whole
   host directory (kolla `docker/base/set_configs.py:131-158,391-393`; see
   [Kolla images §2.3](../../concepts/kolla-images.md#23-kolla_set_configs-copy-and-permissions)). `keystone.conf` keeps
   `domain_specific_drivers_enabled = true` and `domain_config_dir = /etc/keystone/domains` while
   `/etc/kolla/config/keystone/domains` exists (`templates/keystone.conf.j2:24-28`). NOT AVAILABLE (Keystone semantics):
   whether Keystone keeps loading the stale file as a domain config. The task also re-uses the variable name
   `register: keystone_domains` (`config.yml:112,123`), which is an oddity.
9. **Upgrade.** Without serial, all keystone APIs restart at once between `Init` (expand/migrate) and `Finish`
   (contract). With serial, `log_bin_trust_function_creators` is reset to 0 at the end of **every** batch
   (`upgrade.yml:35-48`), while `Enable` runs only in the batch whose first host is `groups['keystone'][0]` (`:6-20`).
   The contract step in the last batch therefore runs with it disabled. Oddity; the impact is NOT AVAILABLE.
10. **Reconfigure re-asserts identity state.** It re-applies the admin credentials and endpoints, and the DB user
    password, from `passwords.yml` and globals. NOT AVAILABLE (os_user and `keystone-manage bootstrap` semantics):
    whether out-of-band changes are silently reverted.

### 3.10 Runtime dependency of other services on Keystone (grep across `ansible/roles/*/templates`)

| Measure | Count | Pattern |
|---|---|---|
| Roles with `www_authenticate_uri` (keystonemiddleware `[keystone_authtoken]`) | **32** | `www_authenticate_uri = {{ keystone_internal_url }}` (28 lines), `.../v3` (6 lines) |
| Roles with `auth_url` | **42** | `auth_url = {{ keystone_admin_url }}` (67 lines), `keystone_internal_url/v3` (8), `keystone_admin_url/v3` (5) |
| Roles with `memcache_servers` / `memcached_servers` | **36** | (41 `memcached_servers =` lines + 7 `memcache_servers =`) |
| Roles with `memcache_secret_key` | **34** | Token cache in memcached with `memcache_security_strategy = ENCRYPT` (for example `ansible/roles/nova/templates/nova.conf.j2:116-130`) |
| Roles that call `service-ks-register` | **39** | During their deploy/reconfigure they create services, endpoints, users, roles and grants through `openstack_auth`, i.e. the Keystone **admin endpoint on the internal VIP:35357**, `run_once`, 5 retries x 10 s (`ansible/roles/service-ks-register/tasks/main.yml:1-120`, `defaults/main.yml:2-47`) |

Implications:
- FACT: the `[keystone_authtoken]` sections of 33 roles point keystonemiddleware at Keystone (the 32 of the table above
  plus monasca, whose section is in the subdirectory template
  `ansible/roles/monasca/templates/monasca-api/api.conf.j2:34-35`), and 35 roles keep its token cache in memcached
  (`memcache_secret_key`; the table's 34 is corrected in the [erratum](index.md#verification-and-errata)). NOT
  AVAILABLE: whether those API services fail to authenticate requests while Keystone or memcached is unavailable.
- Keystone, via the admin endpoint, is a **hard deploy-time dependency** for the `deploy`/`reconfigure` of 39 roles.
- Every service's `memcached_servers` and `transport_url` embed the full memcached and rabbitmq host lists, so changes
  to those groups fan out as restarts across the whole control plane.

## Related

- [verification and errata for all sheets](index.md#verification-and-errata)
- [service index](../../components/index.md)
- [everything marked NOT AVAILABLE](../../troubleshooting/what-is-not-known.md)
