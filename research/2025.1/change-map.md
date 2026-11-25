# Change map 2024.1 → 2025.1 (working notes for the 2025.1 re-study)

Working document, not a site page. It lists what changed between the two studied trees in the parts of the code that
decide what Day-2 commands do, and which 2024.1 pages each change touches. Every item below was checked by reading or
diffing the two source trees; it is a map for the re-study, not a substitute for it: each 2025.1 page must still
re-read its own statements in the 2025.1 sources (CONTRIBUTING.md, "Adding a release").

2024.1 and 2025.1 are both SLURP releases, so the study jumps over 2024.2 (Dalmatian), as an upgrade may. The 145
release notes added between the two tags therefore cover 2024.2 and 2025.1; they were read as pointers only, and every
item below was checked in the code.

## 0. Sources and conventions

| Source | 2025.1 (studied) | 2024.1 (compared against) |
|---|---|---|
| kolla-ansible | tag `2025.1-eom`, commit `7222f0f` (2026-10-22), 20.x, `openstack_release: "2025.1"` (`ansible/group_vars/all.yml:795`) | tag `2024.1-eom`, commit `890396f` (`openstack_release: "2024.1"`, `group_vars/all.yml:679`) |
| kolla (images) | tag `2025.1-eom`, commit `c4b53a2` | tag `2024.1-eom`, commit `ed7a36a` |
| ansible-collection-kolla | tag `2025.1-eom`, commit `09189c7`; kolla-ansible `requirements.yml` pins `stable/2025.1` | tag `2024.1-eom`, commit `82a0f5c` |
| ansible-core | 2.18.20, within `ansible-core>=2.17,<2.19` (`requirements.txt:14`); chosen in lot 1 | 2.16.20 |

Conventions of this file:

- kolla-ansible paths are repository-relative (`ansible/site.yml:95`, `kolla_ansible/cli/commands.py:22`); kolla paths
  start with `docker/`; collection paths start with `roles/` and are marked "collection". "2025.1 `x:n`" is a 2025.1
  line, "2024.1 `x:n`" the old behaviour.
- Labels: [CODE] = read in the code; [NOT AVAILABLE] = the sources do not establish it. Items marked "re-read" are
  pointers for the re-study, not conclusions.
- `git diff --stat 2024.1-eom 2025.1-eom -- ansible/`: 719 files changed, 6709 insertions, 8088 deletions.

## 1. Cross-cutting changes 2024.1 → 2025.1

Short IDs (X1…X22) are used in the impact table (§2).

### X1 — CLI rewritten in Python (cliff); `tools/kolla-ansible` is gone [CODE]

- **No longer holds:** "the CLI is the bash script `tools/kolla-ansible`" (2024.1 `setup.cfg:43-44`, `scripts =`). In
  2025.1 `tools/kolla-ansible` does not exist; `kolla-ansible` is a console script
  (`setup.cfg:43-48`, `kolla-ansible = kolla_ansible.cmd.kolla_ansible:main` at `:48`) built on `cliff`
  (`requirements.txt:27`; `kolla_ansible/cmd/kolla_ansible.py`). Every subcommand is a class in
  `kolla_ansible/cli/commands.py`, registered under `kolla_ansible.cli` (`setup.cfg:50-77`). 138 citations of
  `tools/kolla-ansible` in 39 pages of the 2024.1 study have no target any more (§2).
- The `ansible-playbook` command is built by `kolla_ansible/ansible.py:232-282` (`build_args`) and run by
  `run_playbooks` (`:285-304`). Order of arguments: inventories, `-e @globals.yml`, `-e @passwords.yml`, vault options,
  `-e @globals.d/*` (sorted, `.yml`/`.yaml`/`.json`, `:209-229`), the user's `-e` (`:261-263`), then the command's own
  extra vars (`:264-266`), `-e CONFIG_DIR=…`, `--become`, `--check`, `--diff`, `--limit`, `--skip-tags`, `--tags`, and
  the playbooks last. Compare with 2024.1 `tools/kolla-ansible:599-604`, where `globals.d` came before
  `passwords.yml`. Re-read: `args += [" ".join(playbooks)]` (`ansible.py:281`) passes several `-p` playbooks as one
  argument.
- **Breaking syntax** (release note `python-cli-3e568065b8706e73.yaml`, checked in `commands.py`): the action comes
  first (`kolla-ansible <action> <arguments>`); `mariadb_backup` / `mariadb_recovery` become `mariadb-backup` /
  `mariadb-recovery` (`setup.cfg:72-73`); `--key` is gone (only `--vault-password-file`, `ansible.py:109-116`).
- **Options gone from the CLI:** `--forks` (2024.1 `tools/kolla-ansible:171,382`; no `--forks` in
  `ansible.py:30-125`), the `EXTRA_OPTS` environment variable (2024.1 `:287`) and the `ANSIBLE_SERIAL` variable (X2).
  New options: `-b/--become`, `-J/--ask-vault-password` (`ansible.py:33-37,119-123`).
- **Commands gone:** `rabbitmq-upgrade` and `bash-completion` (2024.1 case labels in `tools/kolla-ansible:400-590`;
  not in `setup.cfg:50-77`); the playbook `ansible/rabbitmq-upgrade.yml` still exists. **Commands new:** `check`
  (X7), `migrate-container-engine`, `migrate-valkey` (`commands.py:495-532`; playbooks
  `ansible/migrate-container-engine.yml`, `ansible/migrate-valkey.yml`), and `stop --ignore-missing`
  (`commands.py:298`, passed as `kolla_action_stop_ignore_missing`, read by
  `ansible/roles/service-stop/tasks/main.yml:10`).
- **No runtime ansible-core check:** 2024.1 refused to run outside 2.15-2.16 (`tools/kolla-ansible:10-11,78-80`); 2025.1
  has no such check in `kolla_ansible/` (the range exists only as a pip requirement, `requirements.txt:14`). Re-read
  whether anything else enforces it before writing it in the checklist page.
- `install-deps` installs both `requirements.yml` and `requirements-core.yml` (`ansible.py:307-318`).
- `KOLLA_CONFIG_PATH` still sets the default `--configdir` (`ansible.py:25,130-136`); the default inventory is
  `<configdir>/ansible/inventory/all-in-one` (`:144-152`).

### X2 — `ANSIBLE_SERIAL` is gone; `upgrade` and `reconfigure` always pass `kolla_serial=0` [CODE]

- 2024.1: `ANSIBLE_SERIAL=${ANSIBLE_SERIAL:-0}` (`tools/kolla-ansible:296`), passed as `-e kolla_serial=…` by
  `upgrade` and `reconfigure` (`:522,531`). The 2024.1 page `operations/controlled-batches.md` (line 149-153) builds
  on it.
- 2025.1: `ANSIBLE_SERIAL = 0` is a module constant (`kolla_ansible/cli/commands.py:20-22`), not read from the
  environment; `Reconfigure` and `Upgrade` set `extra_vars["kolla_serial"] = ANSIBLE_SERIAL` (`:136,278`).
- The command's extra vars come **after** the user's `-e` (X1, `ansible.py:261-266`). With Ansible's "last `-e` wins",
  `kolla-ansible upgrade -e kolla_serial=30%` runs with `kolla_serial=0`. Lot 1 read the ansible-core side too:
  `load_extra_vars` merges the `-e` options in order and `combine_vars` lets the later value replace the earlier one
  (ansible-core 2.18.20 `lib/ansible/utils/vars.py:94-105, :198-224`), so the lot 1 pages state it as [CODE]; the
  **lab test** below only confirms it. Other commands (`deploy`, `bootstrap-servers`, …) set no `kolla_serial`, so a user
  `-e kolla_serial=…` still reaches the plays (the 2025.1 docs show it for `bootstrap-servers`,
  `doc/source/reference/deployment-and-bootstrapping/bootstrap-servers.rst:83`).
- Plays: 47 plays of `site.yml` still read `serial: '{{ kolla_serial|default("0") }}'` (e.g. `ansible/site.yml:95,110`);
  cyborg still reads `serial` (`site.yml:874`). `max_fail_percentage` is on every play as in 2024.1 (153 lines in
  `site.yml`).
- New `kolla_ansible_delegate_facts_hosts: "{{ groups['all'] }}"` (`group_vars/all.yml:43`) chooses which hosts need
  facts under `--limit`: re-read for the compute-scaling page.

### X3 — Container modules: facts actions moved, volumes pre-created with labels [CODE]

- `kolla_container` loses `get_container_env` and `get_container_state` (2024.1 `ansible/library/kolla_container.py:50-51,277-278`);
  2025.1 keeps 13 actions (`kolla_container.py:273-285`). Those reads move to `kolla_container_facts`, which now has
  `get_containers`, `get_containers_env`, `get_containers_state`, `get_containers_names`, `get_volumes`
  (`ansible/library/kolla_container_facts.py:226-231`). `ansible/library/kolla_container_volume_facts.py` is removed.
- Docker worker: before creating a container, every named volume in its `volumes` is created first, with the label
  `kolla_managed: 'true'` (2025.1 `ansible/module_utils/kolla_docker_worker.py:344-346,472-487`). `cpuset_cpus` /
  `cpuset_mems` are compared as strings (`:183-190`), which removes false "differs" results.
- The Podman worker changed by 232 lines and `kolla_toolbox.py` by 346 lines: re-read before any Podman statement.

### X4 — systemd unit template changed again → the first 2025.1 check flags every unit [CODE]

- 2025.1 `ansible/module_utils/kolla_systemd_worker.py:27` adds `PartOf=kolla.target`; the common role installs
  `/etc/systemd/system/kolla.target` (`ansible/roles/common/tasks/config.yml:54-58`).
- `check_unit_change` still compares the whole text of the unit file (`kolla_systemd_worker.py:155-168`) and is part
  of `compare_container`. So, as in the 2023.1 → 2024.1 change (2024.1 map X4), a unit written by 2024.1 code is seen as
  changed at the first 2025.1 check, even with no other difference. Which containers that restarts on a running
  platform: **lab test**.

### X5 — Handlers: `config` no longer notifies; one generic `check-containers` role decides restarts [CODE]

- **No longer holds:** "a changed configuration file notifies the restart handler". In 2024.1, 51 roles notified
  handlers from `tasks/config.yml` (e.g. 2024.1 `ansible/roles/keystone/tasks/config.yml`, 9 `notify`); in 2025.1 only
  one does (`ansible/roles/placement/tasks/config.yml:73-74`, the uWSGI/WSGI file).
- Each role's `check-containers.yml` is now `import_role: service-check-containers`
  (e.g. `ansible/roles/keystone/tasks/check-containers.yml`). That role runs `compare_container` for every enabled
  service mapped to the host (`ansible/roles/service-check-containers/tasks/main.yml:4-28`) and notifies
  `Restart <service> container` for the ones that changed (`:34-41`; the list is built from
  `container_check.results | select('changed')`, so the loop-notify restarts of 2024.1 are gone). 2024.1 had one hand-written task per role
  (e.g. 2024.1 `ansible/roles/keystone/tasks/check-containers.yml:2-17`).
- Consequence for the study: whether a container restarts depends only on `compare_container` (image, container
  options, `kolla_set_configs --check`, unit file), not on which task changed a file. `genconfig` therefore never
  restarts anything (release note `config-handlers-fba9b642c84fc2d7.yaml`). Checked in lot 1: two config tasks still
  notify an unguarded handler (Placement WSGI file with `placement_wsgi_provider: apache`, Cinder Huawei XML files),
  see `start/conventions.md`. The loadbalancer play runs one `check-containers` of the `loadbalancer` role after its
  38 service includes, skipped for `config` (`ansible/site.yml:319-324`).
- The `select_services_enabled_and_mapped_to_host` filter replaces per-task `when` conditions: fewer "skipped" lines in
  a run, so the task counts of `reference/listings/` and of the compute-scaling page must be regenerated.

### X6 — `kolla_set_configs --check` compares more [CODE]

- kolla `docker/base/set_configs.py` (+90 lines): new `ConfigFileCommandDiffers` (the running command, saved in
  `/run_command`, differs from `config.json`) and `StateMismatch` (a file in the defaults state is no longer in
  `config.json`). Both make `--check` report a difference, so `compare_container` (X5) can now ask for a restart when
  only the command or the list of files changed. Permissions get an `exclude` list. `docker/base/start.sh` +3 lines.
- `compare_container` in the shared worker is unchanged apart from the removed actions (X3).

### X7 — `kolla-ansible check` is back [CODE]

- `Check` sets `kolla_action=check` on `site.yml` (`kolla_ansible/cli/commands.py:495-506`). Each role's
  `tasks/check.yml` imports `service-check` (e.g. `ansible/roles/keystone/tasks/check.yml`), which reads the containers
  with `kolla_container_facts` and **fails** the host when a container is missing, not running or unhealthy
  (`ansible/roles/service-check/tasks/main.yml:2-40`).
- A failing check is a failed host, so `max_fail_percentage` and the "whole batch failed" rule apply to a read-only
  command: re-read how far a `check` run goes after the first failure. Real output: **lab test**.

### X8 — Plays: `valkey` added, `swift` removed [CODE]

- 51 plays in both trees; `- name:` diff of `ansible/site.yml`: + "Apply role valkey" (`site.yml:399-411`), − "Apply
  role swift". Line numbers of every later play shift.
- New playbooks: `ansible/migrate-container-engine.yml`, `ansible/migrate-valkey.yml`.

### X9 — ProxySQL is the default database load balancer [CODE]

- `enable_proxysql: "yes"` (2025.1 `group_vars/all.yml:958`; 2024.1 `"no"`). `mariadb_loadbalancer` follows it
  (`:554`), `mariadb_monitor_user` becomes `monitor` (`:545`), `mariadb_backup_target` becomes `replica` (`:555`).
- `enable_mariadb_clustercheck` is no longer set in `group_vars/all.yml`; the mariadb role uses it for the HAProxy
  check (`ansible/roles/mariadb/defaults/main.yml:28,45,64`); its default now lives in the role,
  `'True' if mariadb_loadbalancer == 'haproxy' else 'False'` (`:132`). What an upgrade does with an existing
  `mariadb_clustercheck` container is still to re-read (lot 6).
- Database TLS options are tied to ProxySQL (`group_vars/all.yml:94-95`).
- Upgrade path HAProxy → ProxySQL on a running platform: **lab test** (connection cut, order of plays).

### X10 — MariaDB [CODE]

- `mariadb_innodb_log_file_size_mb: 2048` (`group_vars/all.yml:564`), rendered as `innodb_log_file_size`
  (`ansible/roles/mariadb/templates/galera.cnf.j2:61`). 2024.1 did not set it (no `innodb_log_file_size` in 2024.1 `ansible/roles/mariadb/templates/galera.cnf.j2`), so the server default applied, 96 MB according to the release note. A changed `galera.cnf` means a MariaDB
  restart at the first 2025.1 run that renders it: re-read the mariadb restart path.
- Backups always run on `mariadb_backup_host` (`ansible/roles/mariadb/tasks/backup.yml:35`;
  `ansible/roles/mariadb/defaults/main.yml:123`), new file names (release note
  `mariadb-backup-connect-locally-9f4c2d1e7b3a0c65.yaml`): **lab test** of backup and recovery.

### X11 — RabbitMQ: classic mirrored queues are gone [CODE]

- `om_enable_rabbitmq_high_availability`, `om_enable_rabbitmq_quorum_queues` and
  `om_enable_rabbitmq_transient_quorum_queue` are removed (2024.1 `group_vars/all.yml:266-279`). Services now render
  `rabbit_quorum_queue = true`, `rabbit_transient_quorum_queue = true` and `rabbit_stream_fanout = true`
  unconditionally (e.g. `ansible/roles/nova/templates/nova.conf.j2:151-156`); only
  `om_enable_rabbitmq_stream_fanout: true` remains (`group_vars/all.yml:292`).
- The precheck fails on non-quorum queues (`ansible/roles/rabbitmq/tasks/precheck.yml:118-131`). The migration stays
  manual (message at `:122-123`).

### X12 — HAProxy: TLS 1.3 only by default, layer-7 health checks [CODE]

- `kolla_haproxy_ssl_settings: "modern"` (`group_vars/all.yml:441`) selects `ssl_modern_settings`
  (`:443,457-461`): `no-tlsv12` on bind and server sides, so only TLS 1.3 is accepted. `legacy` and `intermediate`
  restore older settings.
- Layer-7 health checks and a Prometheus `haproxy` user (release note `haproxy_healthchecks_to_l7-b05e8c7b177d1544.yaml`):
  re-read `ansible/roles/haproxy-config/` and the loadbalancer templates.
- Which clients break (including the Quick lab tooling): **lab test**.

### X13 — Removed and new services [CODE]

- **Removed:** role `swift` (and kolla `docker/swift/`), so `components/swift.md` has no subject in 2025.1; the Linux
  Bridge mechanism driver; `prometheus-msteams`.
- **New roles:** `valkey`, `container-engine-migration`, `service-check`, `service-check-containers`,
  `service-image-info`, `service-uwsgi-config` (`comm` of `ansible/roles/` in both tags).
- **New inventory groups:** `[valkey:children] control`, `[nova-metadata:children] nova`,
  `[ovn-sb-db-relay:children] ovn-database` (`ansible/inventory/multinode:191-192,232-233,601-602`). A custom inventory
  copied from 2024.1 lacks them: re-read what the plays do when a group is missing.
- **New containers:** `nova_metadata` (`ansible/roles/nova/defaults/main.yml:33-36`, same image as `nova_api`);
  `ovn_sb_db_relay` (`ansible/roles/ovn-db/defaults/main.yml:31-36`), enabled whenever OVN is
  (`enable_ovn_sb_db_relay: "{{ enable_ovn | bool }}"`, `group_vars/all.yml:953`).
- **Valkey** as a coordination backend is preferred over Redis when enabled (`group_vars/all.yml:573,1164,1178,1205,1403`);
  both default to `"no"` (`:959,965`).
- **Ironic:** `enable_ironic_inspector: "no"`, `enable_ironic_neutron_agent: "no"` (`group_vars/all.yml:908-909`).

### X14 — uWSGI replaces Apache mod_wsgi for several APIs [CODE]

- `nova_wsgi_provider`, `placement_wsgi_provider`, `cinder_wsgi_provider` default to `"uwsgi"`
  (`ansible/roles/nova/defaults/main.yml:324`, `placement/defaults/main.yml:156`, `cinder/defaults/main.yml:387`), with
  the new role `service-uwsgi-config`. Re-read the full list of services and the containers whose command changes (X6).

### X15 — Nova specifics [CODE]

- `ansible/roles/nova/tasks/rolling_upgrade.yml` and `ansible/roles/nova-cell/tasks/post-config.yml` are removed.
  `nova/tasks/upgrade.yml` now renders config, runs `nova_upgrade_checks`, stops the top-level services when
  `nova_safety_upgrade` (`:37-44`), then runs `check-containers` and flushes handlers (`:46-54`).
- New `nova-cell/tasks/version-check.yml`, imported by `deploy.yml:5` and `upgrade.yml:2`: fails when the
  `nova_libvirt` image lacks `/usr/local/bin/kolla_nova_libvirt_start` (`:80-116`, tag `nova-libvirt-script-check`).
- `nova_libvirt` runs `virtlogd` alongside `libvirtd` (release note `nova-libvirt-virtlogd-0b77f24764dcecfc.yaml`):
  re-read the container command and the `qemu.conf` template.

### X16 — Open vSwitch and OVN [CODE]

- `ansible/roles/openvswitch/templates/start-ovs.j2` and `start-ovsdb-server.j2` are removed; both containers now run
  `ovs_wrapper …` (`ansible/roles/openvswitch/templates/openvswitch-vswitchd.json.j2:2`,
  `openvswitch-db-server.json.j2:2`). kolla `docker/openvswitch/openvswitch-db-server/ovs_ensure_configured.sh` is
  gone too. The 2024.1 OVS start sequence must be rewritten from these files.
- OVN: SB relay (X13), new `ovn-db/tasks/config-relay.yml`; `ovn_sb_connection` points at the relays when they are
  enabled (`group_vars/all.yml:646`): re-read which hosts `ovn-controller` talks to after an upgrade.

### X17 — External Ceph: keyrings derived from users [CODE]

- `ceph_cinder_keyring`, `ceph_nova_keyring` and the others are removed; each backend has `cluster` and `user`
  (e.g. `ansible/roles/cinder/defaults/main.yml:281-282`; `group_vars/all.yml:1290-1304`), and the keyring file name
  follows `$cluster.client.$user.keyring`. Re-read the copy tasks of cinder, glance, nova, manila, gnocchi.

### X18 — Prometheus v3 [CODE]

- Container back to `prometheus_server` (`ansible/roles/prometheus/defaults/main.yml:3-4`); the v2 data volume is
  migrated by the upgrade (release note `upgrade-prometheus-to-v3-bdf73866e7a93194.yaml`): re-read
  `prometheus/tasks/upgrade.yml`. Blackbox endpoints are now generated
  (`prometheus_blackbox_exporter_endpoints_default`).

### X19 — ansible-core 2.17-2.18, Python and host operating systems [CODE for the pins only]

- ansible-core 2.17 to 2.18 (`requirements.txt:14`); the kolla-toolbox image ships `ansible-core==2.18.*` (kolla
  `docker/kolla-toolbox/Dockerfile.j2:107`). Every `lib/ansible` citation of the 2024.1 study (2.16.20) must be
  re-read in the version used for the study; none was diffed here.
- Python 3.10 minimum; `distro_python_version: "3"` (`group_vars/all.yml:1382`). Ubuntu 22.04 hosts dropped, Rocky
  Linux 10 added (release notes): re-read `ansible/roles/prechecks/vars/main.yml` for the host list.

### X20 — bootstrap-servers (ansible-collection-kolla) [CODE]

- 33 files changed in `roles/` (collection): new `uninstall.yml` for `docker` and `podman`, SDK install split into
  `docker_sdk/tasks/install.yml` and `podman_sdk/tasks/install.yml`. `bootstrap-servers` uses the system Python
  (release note `use-auto-detected-python-interpreter-for-bootstrap-b83cc25d03e4eeb5.yaml`; re-read
  `kolla_ansible/cli/commands.py:158-170` and `ansible/kolla-host.yml`).

### X21 — Found in lot 1 (2026-11-25) [CODE]

Points that lot 1 found while re-reading `concepts/repository-architecture.md`; they are written in that page.

- **Play order:** `openvswitch`, `ovs-dpdk`, `ovn-controller` and `ovn-db` now run *before* `nova.yml`
  (`ansible/site.yml:605-665`, import at `:667`), and `neutron` right after it (`:669`). In 2024.1 the four network
  plays came after Nova. Re-read in lot 3 (execution flow) and lot 7 (Nova, Neutron).
- **Default `ulimits` on every host:** `default_container_dimensions` now sets `nofile` 1048576 (Docker) or
  `RLIMIT_NOFILE`/`RLIMIT_NPROC` (Podman) on every host (`ansible/group_vars/all.yml:201-224`); 2024.1 did it only on
  Red Hat family hosts (2024.1 `group_vars/all.yml:187-201`). `compare_dimensions` compares ulimits
  (`ansible/module_utils/kolla_container_worker.py:274-303, :326-336`), so with Docker on Debian or Ubuntu every
  container created by 2024.1 that uses the default dimensions differs and is **recreated** at the first 2025.1
  check. The Podman worker filters these two limits out (`kolla_podman_worker.py:219-228, :484-500`).
- **CLI details:** without `-i`, the CLI now passes `<configdir>/ansible/inventory/all-in-one` (2024.1 passed no
  inventory); `globals.d` files now come after `passwords.yml`; `--passwords` is only checked, `build_args` always
  passes `<configdir>/passwords.yml` (`kolla_ansible/ansible.py:191-199, :248-250`); several `-p` are joined into one
  argument (`:281`).
- **Inventory:** `[cyborg:children]` is now `control` only (`ansible/inventory/multinode:146-147`), so 26 groups
  include compute hosts instead of 29.
- **`kolla_set_configs --check`** now reports a dropped `config.json` entry by itself (`StateMismatch`, kolla
  `docker/base/set_configs.py:589-636`); the 2024.1 limit "a dropped entry alone does not report drift" no longer
  holds.

### X22 — Found in lot 3 (2026-11-25) [CODE]

Points that lot 3 found while re-reading the execution flow, tags, batches, compute scaling and findings pages; they
are written in those pages (findings F18 to F20).

- **`-t <service>` no longer restarts HAProxy:** `roles/haproxy-config/tasks/main.yml` has no `notify` any more
  (2024.1 had two). The restart is decided by the final `include_role loadbalancer tasks_from: check-containers` of
  the loadbalancer play (`ansible/site.yml:319-324`), which has no tags of its own and so carries only the play tags
  `haproxy`, `keepalived`, `loadbalancer` (`:115-118`). Under `-t <service>` the service's frontend file in
  `services.d` is rewritten and HAProxy keeps the old one. Ansible's listing agrees
  (`docs/day2/2025.1/reference/listings/list-tasks-nova.txt` lines 106-109).
- **`reconfigure` equals `deploy`:** reconfigure imports `deploy.yml` in 53 of 54 roles (bifrost apart) and no task
  tests `kolla_action == "reconfigure"` alone, so `deploy -e kolla_serial=N` is the batchable form of a reconfigure
  (X2).
- **Loop-notify is gone in Kolla's tasks** (X5): a nova-compute-only override restarts `nova_compute` only, 30
  restarts on 30 computes instead of 90.
- **Memcached:** its settings are in the `command` key of `memcached.json.j2:1-4`, so the new command check (X6) now
  detects a change.
- **`kolla_set_configs --check`** still ignores `permissions` (`handle_permissions`, kolla
  `docker/base/set_configs.py:347`, is not on the check path, `:655-657`).
- **Handlers:** most lost their `kolla_action != "config"` guard; guards remain in etcd, loadbalancer and nova-cell
  `Reload libvirtd` (`ansible/roles/nova-cell/handlers/main.yml:135-141`).
- **Compute scaling:** a no-change `reconfigure -t nova` makes 29 remote invocations per compute (27 in 2024.1), 36 on
  the first compute. New per-compute steps: a container-facts call of the libvirt version check
  (`ansible/roles/nova-cell/tasks/version-check.yml:35-43`) and the `compute_id` block
  (`ansible/roles/nova-cell/tasks/config.yml:53-110`). The `compute_id` block lists **all** hypervisors through
  `kolla_toolbox` on the first conductor, once per compute, with no `run_once` and no `failed_when`, also in
  `genconfig`: C calls of about C entries each.
- **Libvirt version check and `--limit`:** its `run_once` steps are delegated to the first compute of the inventory
  (`version-check.yml:20-21, :97-98`; `ansible/roles/service-image-info/defaults/main.yml:3`), even when that host is
  outside the limit.
- **Facts under `--limit`:** `kolla_ansible_delegate_facts_hosts` (X2) is documented in
  `doc/source/user/ansible-tuning.rst:164-203`, with the rule of thumb that compute runs need the controllers' facts
  only.
- **CLI:** no `--forks`; `forks` comes from `ansible.cfg` or `ANSIBLE_FORKS`. ansible-core 2.17 to 2.18 is accepted
  (`requirements.txt:14`, `ansible/roles/prechecks/vars/main.yml:4-5`).

### X23 — Found in lot 4 (2026-11-25) [CODE]

Points that lot 4 found while re-reading the images and open-questions pages; they are written in
`concepts/kolla-images.md`, `troubleshooting/open-questions.md` (Q22, Q23) and the findings F21 and F22.

- **Defaults state is never pruned (F21):** `kolla_set_configs` saves the original of each destination it overwrites
  and never removes a saved entry. After an entry is dropped from `config.json`, `execute_config_check` (kolla
  `docker/base/set_configs.py:589-642`) raises `StateMismatch` (exit 1) on every check, so the container is restarted
  on every run until it is recreated.
- **Restore swaps saved entries in place** (`set_configs.py:496-498`, `:556`): from the third start on, the saved
  "original" is an earlier rendered file, so dropping an entry leaves a rendered file in place, not the image's file.
  A Python simulation of the code agrees; not run in a container.
- **`kolla_start` installs dev-mode projects** (`docker/base/start.sh:19`, `sudo kolla_install_projects`, which runs
  `pip install -U /dev-mode/*`) before `extend_start` (`:21-24`).
- **`copy_cacerts.sh` rewritten** (`docker/base/copy_cacerts.sh:6-48`): it removes `kolla*` CA files under three
  directories, reads `/var/lib/kolla/share/ca-certificates`, and updates the bundle only if needed. 131 of the 163
  `config.json` templates copy CAs there; `service-cert-copy` no longer notifies a restart.
- **`ovs_wrapper` trap (F22):** `$1` is empty inside the trap handler, so the stop path targets
  `/run/openvswitch/.<pid>.ctl` instead of the daemon's control socket (checked in bash).
- **nova-libvirt:** `kolla_nova_libvirt_start` starts `virtlogd &` then execs libvirtd, and `qemu.conf` sets
  `stdio_handler = "logd"` (Q22: what happens to guest consoles when virtlogd dies).
- **Neutron wrappers:** `neutron_agents_wrappers` (default `no`) runs dnsmasq, haproxy, keepalived and radvd in child
  containers; the netns cleanup is skipped when they are on.
- **Horizon:** the `compress` retry loop is gone; themes are part of the settings hash.
- **systemd:** units carry `PartOf=kolla.target`; `kolla.target` is written by `ansible/roles/common/tasks/config.yml:54-58` and
  never enabled.

### X24 — Found in lot 5 (2026-11-25) [CODE]

Points that lot 5 found while re-reading the shared infrastructure pages; they are written in `components/common.md`,
`operations/apply-common-changes.md`, `components/haproxy-keepalived.md`, `components/openvswitch.md`,
`components/ovn.md`, `components/memcached.md`, `components/iscsi.md`, `components/chrony.md` and fact sheet A.

- **HAProxy under `-t <service>` (F18):** the per-service files are rendered, but the only compare that sees them is
  the last include of the loadbalancer play (`site.yml:319-324`), which carries only the play tags. The new frontend
  waits for the next `-t haproxy`, `-t loadbalancer` or untagged run.
- **Two compares per loadbalancer run:** the role's own `check-containers.yml`, then the final include; both feed one
  handler flush, so HAProxy restarts at most once per run.
- **`any_errors_fatal` on the backup waits** (`roles/loadbalancer/handlers/main.yml:119, :154`): a backup HAProxy or
  ProxySQL that does not come back fails every host, before the master is touched.
- **Keepalived ProxySQL check** now logs in with `proxysql_admin_password`
  (`roles/loadbalancer/templates/keepalived/check_alive_proxysql.sh.j2:6-12`).
- **`external-frontend-map` always listed** in `haproxy.json` (optional unless the single frontend is on), which
  removes the 2024.1 oddity.
- **Removed source files are not compared:** `kolla_set_configs --check` walks the source side of a directory only
  (kolla `docker/base/set_configs.py:213-231`), so the removal of `services.d/mariadb.cfg` does not restart HAProxy by
  itself.
- **OVN Southbound relays:** count = ceil(`ovn-controller` hosts / 50), ports 16641, 16642, …, seeded random choice
  per client; the `ovn-controller` play runs before the `ovn-db` play, so the chassis point at relays before they
  exist on the first 2025.1 run; the 51st `ovn-controller` host adds a relay and moves part of the clients.
- **OVN DB containers gain `environment`:** the first 2025.1 compare is expected to restart every NB, SB and northd
  container at once.
- **OVN availability zones** in `ovn-cms-options` are now joined with `:` instead of `,`
  (`roles/ovn-controller/tasks/setup-ovs.yml:24`).
- **Command check:** memcached settings and OVN command lines written by `genconfig` are now applied by the next
  compare (kolla `docker/base/set_configs.py:580-586`); in 2024.1 they were not.
- **`nova.yml` moved after the OVS and OVN plays** (`site.yml:667`; 2024.1 imported it before openvswitch).
- **First 2025.1 run of `common`:** the three common containers are expected to restart (new CA entries, new fluentd
  command and file names, unit text).
- **`service-cert-copy`:** backend files are copied for `<role>_enable_tls_backend` and `tls-backend` hosts only; no
  task notifies.

## 2. Impact on the 2024.1 pages

69 pages (`find docs/day2/2024.1 -name '*.md'`). "Cited lines" counts the `path:line` citations of the page that
resolve in the 2024.1 trees (kolla-ansible root or `ansible/`, kolla, collection), compared with the same path in
2025.1: **same** = identical text at the same lines; **moved** = the cited text exists elsewhere in the 2025.1 file;
**changed** = cited text not found verbatim (edited, removed, or file gone). Citations relative to a role directory
(most of the fact sheets) and `lib/ansible` citations are not counted; `lib/ansible` always needs a re-read (X19).

"Changes" lists the X items whose keywords appear at least twice in the page: a pointer for the writer, not a
judgement. "Rework": heavy = 30 % or more of the cited lines changed (and at least 15), or 9 X items or more; medium =
15 % or more changed, or 5 X items or more; light = the rest. Pages with a note were checked by hand.

| Page | Changes (keywords) | Cited lines same / moved / changed | Rework | Notes |
|---|---|---|---|---|
| `index.md` | X19, X20 | 0 / 0 / 3 | medium | release identity; all 3 cites are `tools/kolla-ansible` |
| `components/barbican.md` | X5, X11, X12, X13 | 14 / 21 / 11 | medium | |
| `components/chrony.md` | X12, X13, X20 | 17 / 2 / 3 | light | |
| `components/cinder.md` | X2, X4, X5, X6, X11, X12, X17 | 20 / 48 / 34 | heavy | Ceph users (X17), uWSGI (X14), HA precheck `cinder_cluster_name` |
| `components/common.md` | X2, X5, X6, X13, X14, X16, X19 | 13 / 20 / 20 | heavy | `kolla.target` (X4) |
| `components/dependencies.md` | X5, X9, X10, X11, X12, X13, X15, X16, X18, X20 | 41 / 56 / 27 | heavy | ProxySQL, Valkey, OVN relay, swift gone |
| `components/glance.md` | X2, X4, X5, X6, X11, X12, X13, X15, X17 | 25 / 39 / 25 | heavy | Ceph users |
| `components/haproxy-keepalived.md` | X4, X5, X9, X12, X18 | 33 / 18 / 20 | medium | TLS 1.3 only, L7 checks, ProxySQL takes MySQL |
| `components/heat.md` | X2, X4, X5, X6, X11, X12, X14 | 13 / 23 / 15 | medium | |
| `components/horizon.md` | X2, X5, X12 | 12 / 10 / 8 | medium | venus dashboard |
| `components/index.md` | X5, X9, X12, X13, X15, X16, X20 | 7 / 5 / 0 | medium | service cards: remove swift, add valkey |
| `components/iscsi.md` | X5, X6, X13, X20 | 16 / 11 / 5 | light | |
| `components/keystone.md` | X2, X5, X6, X11, X12, X14 | 19 / 21 / 17 | medium | example of X5 (`config.yml` no longer notifies) |
| `components/manila.md` | X5, X13, X17 | 11 / 15 / 12 | medium | Ceph users |
| `components/mariadb.md` | X1, X2, X5, X9, X10, X11, X12, X15, X19 | 47 / 13 / 26 | heavy | ProxySQL default, 2 GB InnoDB log, backup host |
| `components/memcached.md` | X2, X4, X5, X6, X7, X12 | 13 / 7 / 7 | medium | |
| `components/neutron.md` | X2, X5, X13, X15, X16, X19 | 7 / 16 / 10 | medium | Linux Bridge removed |
| `components/nova-deep-dive.md` | X1, X2, X4, X5, X6, X7, X9, X11, X12, X13, X15, X17, X19, X20 | 40 / 71 / 46 | heavy | `rolling_upgrade.yml` gone, `nova_metadata`, libvirt check, uWSGI |
| `components/nova.md` | X2, X4, X5, X6, X11, X12, X13, X15, X20 | 40 / 28 / 29 | heavy | play table |
| `components/octavia.md` | X1, X5, X11, X13 | 43 / 35 / 27 | medium | Valkey/Redis jobboard |
| `components/openvswitch.md` | X2, X5, X15, X16, X19 | 19 / 7 / 8 | medium | start scripts removed: start sequence to rewrite |
| `components/ovn.md` | X2, X5, X6, X16 | 15 / 13 / 8 | medium | SB relay on by default |
| `components/placement.md` | X2, X5, X6, X12, X14 | 13 / 17 / 4 | medium | uWSGI; only role still notifying from config |
| `components/rabbitmq.md` | X1, X2, X5, X11, X15 | 28 / 9 / 20 | heavy | quorum mandatory |
| `components/swift.md` | X2, X4, X5, X6, X12, X13, X15 | 1 / 16 / 40 | heavy | role removed: page dropped or replaced by a "removed in 2025.1" note |
| `concepts/compute-scaling-and-performance.md` | X1, X2, X4, X5, X6, X11, X12, X15, X19, X20 | 48 / 19 / 26 | heavy | `--forks` gone, delegate facts hosts, filtered loops |
| `concepts/deployment-execution-flow.md` | X1, X2, X4, X5, X6, X7, X9, X12, X13, X15, X16, X19 | 75 / 33 / 42 | heavy | CLI flow and handler flow both change |
| `concepts/index.md` | X5, X6 | 0 / 0 / 0 | light | |
| `concepts/kolla-images.md` | X1, X4, X5, X6, X7, X9, X10, X12, X13, X15, X16, X18, X19, X20 | 170 / 93 / 50 | heavy | `set_configs.py` (X6), OVS wrapper |
| `concepts/repository-architecture.md` | X1, X2, X3, X4, X5, X6, X7, X9, X10, X12, X13, X15, X18, X19, X20 | 52 / 31 / 40 | heavy | CLI, modules and roles tables |
| `operations/add-a-compute-node.md` | X5, X19, X20 | 24 / 7 / 7 | medium | |
| `operations/apply-common-changes.md` | X1, X2, X4, X5, X6, X12, X13, X16, X19 | 18 / 18 / 19 | heavy | |
| `operations/change-control-plane-membership.md` | X2, X5, X10, X11, X12 | 22 / 19 / 7 | medium | new groups `valkey`, `ovn-sb-db-relay` |
| `operations/command-quick-lookup.md` | X1, X2, X5, X9, X12, X15, X19 | 28 / 14 / 15 | medium | whole command list (X1) |
| `operations/controlled-batches.md` | X1, X2, X5, X6, X12, X13, X19 | 47 / 25 / 20 | medium | X2 removes its main mechanism: treat as heavy |
| `operations/database-operations.md` | X1, X9, X10, X12 | 27 / 14 / 12 | medium | `mariadb-backup` syntax, ProxySQL |
| `operations/index.md` | X1, X2, X4, X5, X6, X10, X12, X19, X20 | 4 / 7 / 2 | heavy | |
| `operations/pre-execution-checklist.md` | X1, X2, X4, X5, X6, X10, X11, X12, X13, X19 | 15 / 8 / 17 | heavy | no ansible-core runtime check (X1) |
| `operations/predict-a-run.md` | X1, X2, X3, X4, X5, X6, X11, X12, X13, X19 | 15 / 19 / 16 | heavy | genconfig never restarts (X5); `check` (X7) |
| `operations/reconfigure-a-service.md` | X1, X2, X4, X5, X6, X9, X11, X12, X20 | 41 / 16 / 16 | heavy | restart decision (X5, X6) |
| `operations/reconfigure-neutron.md` | X2, X5, X13, X16, X19 | 7 / 14 / 14 | medium | |
| `operations/reconfigure-nova.md` | X1, X2, X4, X5, X6, X11, X12, X15, X19 | 59 / 19 / 25 | heavy | |
| `operations/stop-and-destroy.md` | X1, X4, X13, X15, X19 | 15 / 8 / 7 | medium | `--ignore-missing`, volume labels |
| `operations/update-container-images.md` | X1, X2, X4, X5, X9, X12, X13, X15, X19 | 39 / 29 / 15 | heavy | |
| `reference/factsheets/a-infra-lb-ovn.md` | X1, X2, X4, X5, X6, X7, X9, X11, X12, X16, X18, X19, X20 | 93 / 74 / 48 | heavy | |
| `reference/factsheets/b-mariadb-rabbitmq-keystone.md` | X1, X2, X3, X4, X5, X6, X7, X9, X10, X11, X12, X14, X15, X18, X19 | 79 / 43 / 53 | heavy | |
| `reference/factsheets/c-glance-placement-cinder-horizon-heat.md` | X1, X2, X4, X5, X6, X11, X12, X13, X14, X15, X17, X19, X20 | 46 / 39 / 31 | heavy | |
| `reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md` | X1, X2, X4, X5, X6, X11, X12, X13, X14, X15, X16, X17, X18, X19, X20 | 35 / 55 / 23 | heavy | swift section |
| `reference/factsheets/e-host-bootstrap-ops-playbooks.md` | X1, X2, X4, X5, X6, X10, X11, X12, X13, X15, X17, X19, X20 | 45 / 34 / 38 | heavy | |
| `reference/factsheets/index.md` | X1, X2, X4, X5, X9, X12, X13, X19, X20 | 29 / 9 / 9 | heavy | role list |
| `reference/findings.md` | X2, X4, X5, X6, X11, X13, X15, X19 | 36 / 22 / 28 | heavy | |
| `reference/generated-inventory.md` | X2, X5, X9, X12, X13, X15, X18 | n/a (no line cites) | heavy | regenerate with `tools/extract_kolla_inventory.py` |
| `reference/glossary.md` | X1, X2, X4, X5, X6, X13, X19 | 12 / 20 / 12 | medium | |
| `reference/index.md` | X9, X11, X12, X13, X19, X20 | – | medium | |
| `reference/listings/index.md` | X6, X19, X20 | 1 / 0 / 1 | medium | regenerate with ansible-core 2.18 |
| `reference/method-and-limits.md` | X1, X4, X6, X13, X19, X20 | 1 / 4 / 8 | medium | sources table |
| `risk/index.md` | – | – | light | |
| `risk/risk-register.md` | X1, X2, X3, X4, X5, X6, X11, X12, X13, X15, X16, X19, X20 | 62 / 40 / 77 | heavy | every risk re-rated |
| `risk/small-change-large-workload.md` | X4, X5, X6, X11, X12, X13 | 12 / 8 / 16 | heavy | |
| `risk/tag-index.md` | X10, X12, X13, X16, X20 | 6 / 5 / 0 | medium | new tags `valkey`, `nova-libvirt-script-check` |
| `risk/tags.md` | X1, X2, X4, X5, X6, X9, X10, X11, X12, X13, X15, X16, X18, X19, X20 | 84 / 31 / 35 | heavy | |
| `start/conventions.md` | X1, X3, X5, X10, X13, X19, X20 | 6 / 7 / 7 | medium | |
| `start/find-it-fast.md` | X2, X4, X5, X6, X12, X15, X18 | 6 / 1 / 2 | medium | |
| `start/learning-journey.md` | X2, X4, X5, X6, X9, X11, X12, X13, X15, X19 | – | heavy | stage challenges use the CLI |
| `start/ten-things-to-know.md` | X1, X2, X4, X5, X6, X11, X12, X13, X19 | 11 / 8 / 14 | heavy | |
| `troubleshooting/index.md` | X1, X2, X3, X4, X5, X6, X7, X9, X10, X11, X12, X13, X15, X16, X18, X19, X20 | 100 / 68 / 66 | heavy | |
| `troubleshooting/known-bugs-and-limitations.md` | X1, X2, X4, X5, X6, X9, X12, X13, X15, X18, X19, X20 | 52 / 15 / 40 | heavy | |
| `troubleshooting/open-questions.md` | X1, X4, X5, X6, X11, X12, X13, X15, X16, X19, X20 | 23 / 11 / 11 | heavy | |
| `troubleshooting/what-is-not-known.md` | X1, X4, X5, X6, X7, X11, X12, X13, X15, X16, X19, X20 | 5 / 1 / 3 | heavy | |

Files cited by 2024.1 pages that no longer exist in 2025.1:

| File | Citations | Pages |
|---|---|---|
| `tools/kolla-ansible` | 138 | 39 pages |
| `ansible/roles/swift/**` (16 files) and kolla `docker/swift/**` (2 files) | 54 | `components/swift.md` and 16 others |
| `ansible/roles/openvswitch/templates/start-ovs.j2`, `start-ovsdb-server.j2`; kolla `docker/openvswitch/openvswitch-db-server/ovs_ensure_configured.sh` | 11 | `components/openvswitch.md`, `concepts/kolla-images.md`, `reference/factsheets/a-infra-lb-ovn.md`, `risk/risk-register.md` |
| `ansible/roles/nova/tasks/rolling_upgrade.yml` | 1 | `components/nova-deep-dive.md` |
| `ansible/roles/nova-cell/tasks/post-config.yml` | 1 | `concepts/compute-scaling-and-performance.md` |
| kolla `docker/haproxy/haproxy-ssh/update-haproxy-cert.sh` | 1 | `reference/factsheets/a-infra-lb-ovn.md` |

## 3. Suggested lots for the re-study

Same order as the 2024.1 re-study: foundations first, because the other pages link to and reuse their statements.

1. **Lot 1 — Method and foundations:** `reference/method-and-limits.md`, `concepts/repository-architecture.md`
   (X1, X3, X4, X5), `reference/glossary.md`, `start/conventions.md`. Decide here how to write commands (new syntax
   only, with a one-line note on the 2024.1 form) and whether `components/swift.md` is dropped or kept as a short
   "removed" page.
2. **Lot 2 — Regenerated material:** `reference/listings/index.md` (ansible-core 2.18 listings),
   `reference/generated-inventory.md`, component service cards / `components/index.md`, `risk/tag-index.md`.
3. **Lot 3 — Execution model:** `concepts/deployment-execution-flow.md`, `risk/tags.md`,
   `operations/controlled-batches.md`, `concepts/compute-scaling-and-performance.md`, `reference/findings.md`
   (X1, X2, X5, X7, X19).
4. **Lot 4 — Images and start path:** `concepts/kolla-images.md`, `troubleshooting/open-questions.md` (X6, X16).
5. **Lot 5 — Shared infrastructure:** `components/common.md`, `operations/apply-common-changes.md`,
   `components/haproxy-keepalived.md`, `reference/factsheets/a-infra-lb-ovn.md`, `components/openvswitch.md`,
   `components/ovn.md`, `components/chrony.md`, `components/iscsi.md`, `components/memcached.md` (X4, X12, X16).
6. **Lot 6 — Stateful services:** `components/rabbitmq.md`, `components/mariadb.md`, `operations/database-operations.md`,
   `operations/change-control-plane-membership.md`, `components/keystone.md`,
   `reference/factsheets/b-mariadb-rabbitmq-keystone.md` (X9, X10, X11).
7. **Lot 7 — Nova and Neutron:** `components/nova-deep-dive.md`, `components/nova.md`, `operations/reconfigure-nova.md`,
   `components/neutron.md`, `operations/reconfigure-neutron.md`, `operations/add-a-compute-node.md` (X14, X15).
8. **Lot 8 — Other services:** `components/cinder.md`, `glance.md`, `manila.md`, `horizon.md`, `octavia.md`,
   `placement.md`, `heat.md`, `barbican.md`, `swift.md`, `reference/factsheets/c-…md`, `reference/factsheets/d-…md`,
   `reference/factsheets/index.md`, `components/dependencies.md` (X13, X14, X17, X18).
9. **Lot 9 — Host and ops playbooks:** `reference/factsheets/e-host-bootstrap-ops-playbooks.md`,
   `operations/update-container-images.md`, `operations/stop-and-destroy.md`, `operations/predict-a-run.md`,
   `operations/reconfigure-a-service.md`, `operations/pre-execution-checklist.md`, `operations/command-quick-lookup.md`
   (X1, X7, X20).
10. **Lot 10 — Synthesis pages (last):** `risk/risk-register.md`, `risk/small-change-large-workload.md`,
    `troubleshooting/index.md`, `troubleshooting/known-bugs-and-limitations.md`,
    `troubleshooting/what-is-not-known.md`, `start/ten-things-to-know.md`, `start/learning-journey.md`,
    `start/find-it-fast.md`, `operations/index.md`, `concepts/index.md`, `components/index.md` (text),
    `reference/index.md`, `risk/index.md`, `index.md`.

## 4. Lab tests

The study rests on reading code; these points stay [NOT AVAILABLE] in the pages until a lab run confirms them. They
need a lab installed in 2024.1 and upgraded to 2025.1 (the Quick lab deploys 2026.1).

| Test | Change | What the code does not settle |
|---|---|---|
| `kolla-ansible upgrade -e kolla_serial=30%` | X2 | confirm that the plays see 0, as the code says |
| First `deploy` after the upgrade on Ubuntu or Debian with Docker | X4, X21 | which containers are recreated by the new default `ulimits`, and for how long the services are down |
| Upgrade 2024.1 → 2025.1 with HAProxy → ProxySQL | X9 | MySQL connection cut, fate of `mariadb_clustercheck` |
| First `reconfigure` after the upgrade, with no config change | X4, X5, X6 | which containers actually restart |
| `kolla-ansible check` on a healthy lab, then with one container stopped | X7 | real output, how far the run goes |
| Switch to uWSGI (Nova, Placement, Cinder) | X14 | API downtime during the switch |
| `ovn-sb-db-relay` added during the upgrade | X13, X16 | `ovn-controller` reconnection |
| MariaDB with a 2 GB InnoDB log | X10 | disk use, restart and crash recovery time |
| `mariadb-backup` then `mariadb-recovery` | X1, X10 | file names, end-to-end restore |
| HAProxy `modern` TLS profile | X12 | clients that cannot do TLS 1.3 |
| Prometheus v2 → v3 | X18 | data kept from the `prometheus_v2` volume |
| Change a frontend option, `deploy -t keystone`, then `deploy -t haproxy` | X5, X22 | whether HAProxy keeps the old frontend after the first run and applies it at the second |
| nova-compute-only override, `deploy -t nova` | X5, X22 | whether only `nova_compute` restarts, not `nova_libvirt` and `nova_ssh` |
| `reconfigure -t nova` with many computes; `genconfig` with the Nova API down | X22 | time and load of the per-compute hypervisor list on the first conductor and the Nova API; whether `genconfig` fails |
| `deploy -t nova --limit <compute>` with `kolla_ansible_delegate_facts_hosts` set to the controllers | X2, X22 | same rendered files as with the default list |
| `deploy -t nova --limit <a compute other than the first>` | X22 | the version check's one-shot containers start on the first compute, outside the limit |
| Drop a `config.json` entry, run `reconfigure` twice | X23 | whether each run restarts the container (F21) and which file stays at the destination |
| `docker stop openvswitch_vswitchd` | X16, X23 | whether the `ovs_wrapper` trap stops the daemon cleanly or the stop times out (F22) |
| Kill `virtlogd` inside `nova_libvirt` with a running guest | X15, X23 | guest console and log behaviour (Q22) |
| Remove a CA from `kolla_copy_ca_into_containers`, `reconfigure` | X23 | whether the CA leaves the container bundle |
| Horizon deploy with a slow `compress` | X23 | failure without the old retry loop |
| Change a keystone frontend option, `reconfigure -t keystone`, then `reconfigure -t haproxy` | X24 | whether HAProxy keeps the old frontend after the first run and applies it at the second (F18) |
| Stop HAProxy on a backup during a `reconfigure -t haproxy` | X24 | whether `any_errors_fatal` stops the play on every host before the master is touched |
| Change `proxysql_admin_password`, `reconfigure -t loadbalancer` | X24 | whether keepalived's ProxySQL check fails and the VIP moves |
| Enable ProxySQL on a cloud that had `mariadb.cfg` | X24 | whether the old `mariadb` frontend stays loaded in HAProxy |
| Upgrade 2024.1 → 2025.1 with OVN, relays on | X16, X24 | how long the chassis stay without a Southbound connection between the `ovn-controller` and `ovn-db` plays |
| Add the 51st `ovn-controller` host | X24 | reconnection of the chassis and agents whose relay changes |
| First 2025.1 run on an OVN cloud | X24 | whether every NB, SB and northd container restarts at once, and RAFT recovery |
| `neutron_ovn_availability_zones` with two zones, first 2025.1 run | X24 | how Neutron reads `a:b` instead of `a,b` |
| First 2025.1 `reconfigure -t common` | X24 | whether `fluentd`, `cron` and `kolla_toolbox` restart, and for how long logs are lost |
