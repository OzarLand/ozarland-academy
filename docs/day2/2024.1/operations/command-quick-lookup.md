---
title: Command quick lookup by tag
description: "In 2024.1, one row per command and tag, with the hosts touched, the containers that can restart, the one-shot containers and what scales the work."
tags: [tags, reconfigure, deploy-containers, genconfig, pull, one-shot, keystone, glance, placement, nova, neutron, openvswitch, haproxy, letsencrypt, chrony, common, mariadb, rabbitmq, etcd]
impact: [restarts-on-drift, writes-config, pulls-images]
---

# Command quick lookup by tag

One row per command: the hosts it touches with the 2024.1 `multinode` example inventory, the containers that can
restart, the one-shot containers it runs and what scales its work. Fifteen rows are `-t <tag> reconfigure` (the
`-t chrony` row is kept to record that the tag still selects nothing in 2024.1; `-t letsencrypt` and `-t etcd` are new
rows); the last four are `reconfigure` without a tag, `deploy-containers`, `genconfig` and `pull`. Each row is checked
against the 2024.1 code; [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) gives the full detail.

Still holds in 2024.1: no row brings the `common` containers along except `-t common` and `reconfigure` without a tag.
`common` is a play of its own, tagged `common` (`site.yml:88-103`), and no role declares a dependency (there is no
`roles/*/meta` directory in 2024.1). "haproxy" below is the `loadbalancer` group (the `network` hosts in `multinode`,
`inventory/multinode:84-85`), reached through the per-service `include_role … tasks_from: loadbalancer` of the
loadbalancer play, which runs only with `enable_haproxy` and for `deploy`, `reconfigure`, `upgrade` and `config`
(`site.yml:105-326`, condition at `:324-326`). Every play now carries `max_fail_percentage`, default 100, which does not
change what a row touches ([Write config first, apply in controlled batches
§1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).

No row exists for the services removed in 2024.1 (freezer, monasca, murano, sahara, senlin, solum, vitrage, kafka,
storm, zookeeper, outward RabbitMQ): their roles are gone from `ansible/roles/` and no play selects them, so their tags
run only the `always` plays ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)) [CODE].

The table follows the [conventions of the command sections](index.md#conventions-used-by-the-command-sections), which
also say what the examples assume: "Can restart" is the **Restarts** convention, containers that can restart, only if
[drift](index.md#drift) is detected. "Typical duration driver" names what the amount of work grows with, read from the
hosts and tasks a run covers; no run was timed, so durations themselves are [NOT AVAILABLE].

| Command | Hosts touched (default inventory) | Can restart | One-shot containers | Typical duration driver |
|---|---|---|---|---|
| `-t keystone reconfigure` | haproxy, control (`keystone` group, `inventory/multinode:93-94`; play `site.yml:483-495`) | keystone, keystone_ssh, keystone_fernet (`roles/keystone/handlers/main.yml:29-75`), haproxy | `bootstrap_keystone` (db sync, kolla `docker/keystone/keystone/extend_start.sh:43-46`), `run_once` (`roles/keystone/tasks/bootstrap_service.yml:33-50`); `bootstrap_keystone_fernet` only when no `keystone_fernet` container is running (`:52-75`) | small |
| `-t glance reconfigure` | haproxy, `glance-api` (control, `inventory/multinode:223-224`; play `site.yml:544-556`) | glance-api (and glance-tls-proxy when enabled, `roles/glance/handlers/main.yml:2, :20`), haproxy | `bootstrap_glance` (db sync + metadefs load, kolla `docker/glance/glance-api/extend_start.sh:5-9`), between two `kolla_toolbox` calls that set and reset the MariaDB global `log_bin_trust_function_creators`, unless `use_preconfigured_databases` (`roles/glance/tasks/bootstrap_service.yml:2-54`) | small |
| `-t placement reconfigure` | haproxy, control (`inventory/multinode:171-172`; play `site.yml:593-605`) | placement-api, haproxy | db sync + online data migrations in one `bootstrap_placement` container (`roles/placement/tasks/bootstrap_service.yml:2-20`; kolla `docker/placement/placement-api/extend_start.sh:5-9`) | small |
| `-t nova reconfigure` | haproxy, control, **all computes** | all nova incl. **libvirt**, haproxy | 6 runs (those of `nova-api` and `nova-cell` below) when cell0 and the cell are unchanged | number of computes |
| `-t nova-api reconfigure` | haproxy, control (`nova.yml:29-65, :103-122, :152-172`) | nova-api, scheduler (super-conductor only with `enable_cells`), haproxy | 3: API DB sync (`roles/nova/tasks/bootstrap.yml:54`, `bootstrap_service.yml:2-21`), `map_cell0` and a `list_cells` for cell0 (`map_cell0.yml:3-30`; `roles/nova-cell/tasks/get_cell_settings.yml:2-21`); `update_cell` for cell0 and a second API DB sync only on change (`map_cell0.yml:32-67`) | small |
| `-t nova-cell reconfigure` | haproxy (console-proxy frontends, `site.yml:259-265`), control (conductor, consoles), **all computes** (`nova.yml:125-147`) | conductor, consoles, compute, libvirt, ssh; haproxy if a console-proxy frontend changed | 3: cell DB sync (`roles/nova-cell/tasks/bootstrap_service.yml:2-21`), `list_cells` ×2: cell lookup (`create_cells.yml:2-4`) and discovery (`discover_computes.yml:4-5`, once per batch that holds computes, `wait_discover_computes.yml:87-90`); `create_cell`/`update_cell` only when the cell is missing or its URLs changed (`create_cells.yml:6-55`); `discover_hosts` itself is an `exec` into `nova_conductor` (`discover_computes.yml:14-18`) | number of computes |
| `-t neutron reconfigure` | haproxy, control, network, **all computes** (play hosts include `compute` and `manila-share`, `site.yml:671-693`) | server, all agents, haproxy | `bootstrap_neutron` (`neutron-db-manage upgrade head` for neutron and each enabled subproject). Still holds in 2024.1: it runs on every deploy **and reconfigure**, whatever `neutron_enable_rolling_upgrade` (`roles/neutron/tasks/reconfigure.yml:2`, `deploy.yml:20`, `bootstrap.yml:38`, `bootstrap_service.yml:2-21`, no `when`) | number of computes |
| `-t openvswitch reconfigure` | network, **all computes** (`openvswitch` group, `inventory/multinode:105-108`; play `site.yml:611-624`, only while `enable_ovs_dpdk` is off) | openvswitch_db/vswitchd (`roles/openvswitch/handlers/main.yml:2-44`); a changed `system-id`, `hostname` or `hw-offload` restarts vswitchd (`post-config.yml:22-23`) | – | number of computes |
| `-t haproxy reconfigure` | haproxy (`site.yml:105-120`) | haproxy, keepalived, proxysql when enabled (backup hosts before the master, `roles/loadbalancer/handlers/main.yml:36-318`); new: haproxy_ssh with `enable_letsencrypt` (`roles/loadbalancer/defaults/main.yml:29-36`, `handlers/main.yml:331-345`) | – | small |
| `-t letsencrypt reconfigure` (new) | only with `enable_letsencrypt` (default `"no"`, `group_vars/all.yml:796`): haproxy (letsencrypt include, `site.yml:208-212`) and the `letsencrypt` group, a child of `loadbalancer` (`inventory/multinode:192-193`; play `site.yml:328-340`) | letsencrypt_webserver, letsencrypt_lego (`roles/letsencrypt/handlers/main.yml`), haproxy if its frontend changed; not haproxy_ssh, which belongs to the loadbalancer play | – (`roles/letsencrypt/tasks/deploy.yml:2-7`) | small |
| `-t chrony reconfigure` | none: still no `chrony` role or play in 2024.1 (only the `always`-tagged plays run) | – | – | – |
| `-t common reconfigure` | **all hosts** of the `common` group (`site.yml:88-103`; `inventory/multinode:49-54, :203-213`) | fluentd, cron, kolla_toolbox (all three on drift, loop-notify, `roles/common/tasks/check-containers.yml:2-17`) | –; new in 2024.1: `ensure_image` pulls the fluentd image when it is absent (`roles/common/tasks/config.yml:42-51`) | number of hosts |
| `-t mariadb reconfigure` | haproxy, mariadb | mariadb (restart play with `serial: "33%"`: one host per batch with 3 nodes, `mariadb.yml:18-34`; ansible-core 2.16.20 `lib/ansible/utils/helpers.py:32`), clustercheck (enabled with `enable_haproxy`, `roles/mariadb/defaults/main.yml:132`), haproxy | – | Galera sync |
| `-t rabbitmq reconfigure` | haproxy, rabbitmq (no outward RabbitMQ any more: `rabbitmq.yml:3-70` has three plays) | rabbitmq one by one (`serial: "33%"`, each node drained first: `rabbitmq.yml:30-49`, `roles/rabbitmq/tasks/restart_services.yml:9-17`), haproxy | `rabbitmq_version_check` on the first RabbitMQ host when the container exists (`roles/rabbitmq/tasks/deploy.yml:2`, `version-check.yml:18-36, :75-78`); `rabbitmq_bootstrap` only for a new volume (`bootstrap.yml:10-26`) | broker start |
| `-t etcd reconfigure` (new) | only with `enable_etcd` (default `"no"`, `group_vars/all.yml:764`): haproxy (etcd include, `site.yml:163-167`), `etcd` hosts (control, `inventory/multinode:62-63`; play `site.yml:470-481`, no `serial`) | etcd: non-leaders in `% 4` waves, then the leader (`roles/etcd/handlers/main.yml:40-65`); not batched by `ANSIBLE_SERIAL`; haproxy if its frontend changed | –; a new cluster or a member without a volume is bootstrapped by starting the `etcd` container itself (`roles/etcd/tasks/bootstrap.yml:9-25`, `bootstrap_cluster.yml:2-14`) | cluster size |
| `reconfigure` (no tag) | all | everything that drifted | db sync of every enabled service, neutron included (see the neutron row), the 6 nova runs, `rabbitmq_version_check` | number of hosts × tasks |
| `deploy-containers -t X` | X's hosts, no haproxy include (`site.yml:324-326`); no `kolla_serial` is passed (`tools/kolla-ansible:499-502`) | X (drifted only): the role runs only its container check (e.g. `roles/keystone/tasks/deploy-containers.yml:1-2`) | none | small per host |
| `genconfig -t X` | X's hosts (+haproxy) (`tools/kolla-ansible:557-559`, `kolla_action=config`) | none: restart handlers skip `kolla_action == "config"` (e.g. `roles/keystone/handlers/main.yml:74-75`, `roles/rabbitmq/handlers/main.yml:5-6`) | none; new: `-t common` can pull the fluentd image (`roles/common/tasks/config.yml:42-51`) | templating |
| `pull -t X` | X's hosts (`tools/kolla-ansible:516-518`) | none | none | image size × hosts |

## Related

- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) — the master table: what each tag executes and
  on which hosts
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) — per-tag
  answers: files, VMs, APIs, networking and storage, safety, prerequisites
- [Tag index](../risk/tag-index.md) — each tag with its component page
- [Operations catalogue](index.md#operations-catalogue) — the operation pages, with their full command lines
- [Predict and inspect a run](predict-a-run.md) — how to see what will restart before running one of these commands
- [Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) — what each
  one-shot container runs
- [Compute scaling §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)
  — the work per compute host, read from the task files
