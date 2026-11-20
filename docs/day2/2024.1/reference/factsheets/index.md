---
title: Per-role fact sheets
description: "Five per-role fact sheets, re-studied against 2024.1-eom, how they were checked, and the eleven corrections with their 2024.1 status."
tags: [evidence, haproxy, keepalived, loadbalancer, letsencrypt, memcached, chrony, ovn, mariadb, rabbitmq, keystone, glance, placement, cinder, horizon, heat, barbican, octavia, swift, manila, bootstrap-servers, prechecks, destroy]
---

# Per-role fact sheets

Five fact sheets first produced by systematic source reading of `ussuri-eol`, re-studied against `2023.1-eol`, and
re-studied again against `2024.1-eom`: each 2023.1 statement was looked up in the 2024.1 sources and re-checked there.
Every **FACT** carries a `path:line` reference relative to the kolla-ansible repository root, the kolla image repository
(kolla `docker/...`), ansible-collection-kolla (`ansible-collection-kolla roles/...`) or the Ansible source
(ansible-core 2.16.20 `lib/ansible/...`). Anything these sources do not establish is labelled **NOT AVAILABLE**.

| Sheet | Scope |
|---|---|
| [A — infra / load balancing / OVN](a-infra-lb-ovn.md) | `loadbalancer` (haproxy, keepalived, proxysql and, new in 2024.1, `haproxy-ssh`; the Ussuri `haproxy` role, which no longer exists), the 39 per-service `loadbalancer.yml` includes, `loadbalancer-config`, `haproxy-config`, `proxysql-config`, `letsencrypt` (new in 2024.1), `memcached`, `chrony` (no role in 2024.1), `ovn-controller` and `ovn-db` (the Ussuri `ovn` role), `ovs-dpdk`, `service-cert-copy`, `certificates.yml` |
| [B — MariaDB / RabbitMQ / Keystone](b-mariadb-rabbitmq-keystone.md) | Galera bootstrap/recovery/backup and rolling restart; RabbitMQ (quorum queues on by default in 2024.1; the outward RabbitMQ is gone); Keystone fernet keys and runtime coupling |
| [C — Glance / Placement / Cinder / Horizon / Heat](c-glance-placement-cinder-horizon-heat.md) | per-role flow, bootstrap on reconfigure, dependencies, restart impact |
| [D — Barbican / Octavia / Swift / Manila + compute-side roles](d-barbican-octavia-swift-manila-compute-roles.md) | control-plane roles and every role that places containers on compute hosts; templates embedding host lists |
| [E — host bootstrap and operational playbooks](e-host-bootstrap-ops-playbooks.md) | `bootstrap-servers` (the ansible-collection-kolla roles `baremetal`, `docker` or, new in 2024.1, `podman`, `etc_hosts` and others: Docker restart conditions, `/etc/hosts`), prechecks, destroy, prune-images, fact gathering, CLI, tuning docs |

The roles named above as gone or new are shown by the 2024.1 tree [CODE]: `ansible/roles/` has no `haproxy`, `chrony`
or `ovn` directory, and has `loadbalancer`, `proxysql-config`, `hacluster`, `letsencrypt`, `ovn-controller` and
`ovn-db`; `kolla-host.yml:4-14` applies `openstack.kolla.baremetal`, whose engine role is chosen from
`kolla_container_engine` (ansible-collection-kolla `roles/baremetal/defaults/main.yml:37`,
`roles/baremetal/tasks/install.yml:38`).

To go from a service or a tag to the right sheet section, use the [service index](../../components/index.md) and the
[tag index](../../risk/tag-index.md).

> [!NOTE]
> **Key answers**
>
> - **Eleven corrections to the Ussuri fact sheets**, each restated for 2024.1 below ([Corrections](#corrections)).
> - **The one with the widest effect still stands reversed in 2024.1:** a stop uses `docker_graceful_timeout` (60 s),
>   through each container's systemd unit, now written by the `kolla_container` module; the Ussuri effective timeout of
>   10 s does not apply ([F3](../findings.md#f3)). The unit text itself changed in 2024.1, which makes the first 2024.1
>   check restart a container whose unit 2023.1 wrote ([F16](../findings.md#f16)).

## Verification and errata

How the sheets were checked:

- **Spot checks against the source.** The five Ussuri spot checks, re-read in 2024.1 [CODE]:
  - MariaDB restart waves `index % 4`: **gone since 2023.1, still gone in 2024.1**. The handlers only sort hosts into
    groups (`mariadb_bootstrap_restart`, `mariadb_restart`, `mariadb_start`; `roles/mariadb/handlers/main.yml:51-73`),
    and separate plays restart them with `serial: "33%"` (`mariadb.yml:18-52`); no `% 4` remains in the role or the
    playbook. New in 2024.1, these plays set `max_fail_percentage`, default 100 (`mariadb.yml:25-28`), which never stops
    a play early ([Controlled batches](../../operations/controlled-batches.md));
  - glance `log_bin_trust_function_creators` toggle: still there
    (`roles/glance/tasks/bootstrap_service.yml:2,12,39,49`);
  - Docker restart gate in `bootstrap-servers`: still in ansible-collection-kolla. `daemon.json` and the registry CA
    notify `Restart docker` (ansible-collection-kolla `roles/docker/tasks/config.yml:9-53,104-115`), which restarts the
    daemon, or reloads it when `docker_systemd_reload` is set (default `false`)
    (`roles/docker/handlers/main.yml:10-15`, `roles/docker/defaults/main.yml:65`). New in 2024.1, `daemon.json` can also
    carry `docker_debug` (`roles/docker/tasks/config.yml:46`);
  - keepalived priority from inventory index: still there
    (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`);
  - compute-side memcached lists: still there (`roles/ceilometer/templates/ceilometer.conf.j2:69`).
- **Ansible behaviours** that the sheets rely on are cited to the ansible-core 2.16.20 source where it shows them, and
  are marked NOT AVAILABLE where it does not. ansible-core 2.14.18, used for 2023.1, is not on disk, so no statement
  says what changed inside ansible-core itself.

**Erratum (sheets A, B and E, and any statement that `docker stop` honours `docker_graceful_timeout: 60`).**
**Ussuri:** the effective stop timeout of every `kolla_docker` stop/restart was **10 s**, because the argument spec set
`default=10` and a non-`None` module parameter overrode `common_options`. **2024.1: the erratum still does not apply**
[CODE], as in 2023.1. `kolla_docker` is replaced by `kolla_container`, whose `graceful_timeout` and `client_timeout`
are declared without a default (`library/kolla_container.py:313,335`); the merge takes the `common_options` values and
falls back to 10 and 120 only when those are absent (`:361-391`, fallback values at `:370-371`):
`docker_graceful_timeout: 60` and `docker_client_timeout: 120` (`group_vars/all.yml:105,139,151-152`). Containers other
than one-shots run under a systemd unit `kolla-<name>-container.service` whose `ExecStop` is
`/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:20-39`; the engine is
`docker` by default, `:50-54`); a container without a unit file is stopped by the Docker client with the same timeout,
10 s only when none is passed (`module_utils/kolla_docker_worker.py:415-431`). `docker_client_timeout` is a working knob
too: it is the Docker client timeout (`module_utils/kolla_docker_worker.py:34`) and the time the module waits for a
unit to reach its state (`module_utils/kolla_systemd_worker.py:64,103,112`). A sheet statement of 60 s therefore
matches 2024.1, and one of 10 s describes Ussuri only ([F3](../findings.md#f3), [R24](../../risk/risk-register.md#r24)).

**Erratum (sheet A, "There is no reload path anywhere in scope").** Still holds in 2024.1 [CODE]. It is true for the
handler path: every handler stops and starts or recreates its container, and `kolla_container` has no reload action
(`library/kolla_container.py:273-287`). Outside the handlers, Kolla sends one signal: the "Refresh nova scheduler cell
cache" play sends `SIGHUP` to `nova_scheduler` on the nova-scheduler hosts. It does so on `deploy` and `reconfigure`
runs that select the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag, or no tag (`nova.yml:152-172`,
`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`).

**Erratum (sheet B [§3.10][sheet-b-310], memcached counts).** **Ussuri:** 35 roles had `memcache_secret_key` in their
templates, 37 had `memcache_servers`/`memcached_servers`, and 38 embedded the memcached host list. **2023.1:** 29, 32
and 33. **2024.1** [CODE, `grep` across `roles/*/templates`]: **23** roles have `memcache_secret_key`, **26** have
`memcache_servers`/`memcached_servers`, and **27** embed the memcached host list, all by looping over
`groups['memcached']` in their templates; the six fewer are the removed roles freezer, murano, sahara, senlin, solum and
vitrage. This includes horizon, whose settings template is now `_9998-kolla-settings.py.j2` and whose
`CACHES['default']['LOCATION']` uses the loop when `horizon_backend_database` is off
(`roles/horizon/templates/_9998-kolla-settings.py.j2:19-23`). A 28th role, telegraf, names the group only to test
whether the host itself runs memcached (`roles/telegraf/templates/telegraf.conf.j2:54-57`). The list still includes
`neutron.conf` (`roles/neutron/templates/neutron.conf.j2:123`), which the neutron agents on compute hosts also read, so
a
memcached membership change reaches computes ([Memcached](../../components/memcached.md)).

**Erratum (sheet A, "`tags: always` on the `import_role: haproxy-config` in every `loadbalancer.yml`").** In 2024.1
there are 39 `loadbalancer.yml` files (44 in 2023.1), and each imports `loadbalancer-config` (not `haproxy-config`)
with `tags: always`; `loadbalancer-config` then imports `haproxy-config` and `proxysql-config` under conditions
(`roles/loadbalancer-config/tasks/main.yml:2-8`). 38 do it directly (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`;
ceph-rgw writes `role:` instead of `name:`, `roles/ceph-rgw/tasks/loadbalancer.yml:2-7`).
`roles/nova-cell/tasks/loadbalancer.yml` reaches it through a chain: `import_tasks: proxy_loadbalancer.yml`, then a
looped `include_tasks: cell_proxy_loadbalancer.yml` (`roles/nova-cell/tasks/proxy_loadbalancer.yml:6`), then
`import_role: loadbalancer-config` (`roles/nova-cell/tasks/cell_proxy_loadbalancer.yml:3-12`), with `tags: always` at
every level. The effect is the same [CODE]
([Tags §2.3](../../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)).

**Erratum (image-side statements, kolla read later).** The kolla image sources were read after the Ussuri sheets were
written. Re-read in kolla `2024.1-eom` [CODE]:
- sheet A: **changed in 2024.1**, keepalived's `/check_alive.sh` no longer queries the haproxy stats socket itself: it
  runs every script under `/checks` and fails if one fails (kolla `docker/keepalived/check_alive.sh:9-32`; the legacy
  branch is gone). The socket query moved to a script that kolla-ansible renders into that directory
  (`roles/loadbalancer/templates/keepalived/check_alive_haproxy.sh.j2:6`, `roles/loadbalancer/tasks/config.yml:97-98`,
  mounted at `/checks` by `roles/loadbalancer/templates/keepalived/keepalived.json.j2:11-12`). The haproxy image still
  ships a reload helper (kolla `docker/haproxy/haproxy/ensure_latest_config.sh:5-12`) that no file under kolla-ansible
  2024.1 `ansible/` calls;
- sheet B: the broker's `.erlang.cookie` file is written only by the RabbitMQ bootstrap container, never on a normal
  broker start (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`);
- sheet C: the placement bootstrap container also runs `db online_data_migrations`, on every deploy and reconfigure
  (kolla `docker/placement/placement-api/extend_start.sh:5-9`). The glance bootstrap adds `db_load_metadefs` (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`). The heat bootstrap creates the heat domain and user only when the
  domain is absent (kolla `docker/heat/heat-api/extend_start.sh:5-17`). Horizon runs `collectstatic` only when its
  settings hash is missing or differs, a dashboard plugin is added or removed, or `FORCE_GENERATE=yes` (kolla
  `docker/horizon/extend_start.sh:32-46,215-258`;
  [Kolla images §5.2](../../concepts/kolla-images.md#52-horizon-static-assets));
- sheet D: swift config and rings are copied into a container only at its start (kolla `docker/base/start.sh:11`,
  `docker/base/set_configs.py:535-551`; both files are identical to 2023.1's). Only `swift_rsyncd` fixes `/srv/node`
  ownership at start (kolla `docker/swift/swift-rsyncd/extend_start.sh:3`).

In the same Ussuri pass, sheet E [§11](e-host-bootstrap-ops-playbooks.md#11-toolskolla-ansible-cli) was corrected: like
`reconfigure`, `upgrade` overrides a user `-e kolla_serial`. This still holds in 2024.1 [CODE]: a user `-e` is added to
`EXTRA_OPTS` while the options are parsed (`tools/kolla-ansible:366-368`), and `upgrade` and `reconfigure` then append
`-e kolla_serial=${ANSIBLE_SERIAL}` after it (`:522`, `:531`; command line at `:604`). Statements that cite a kolla path
(kolla `docker/...`, relative to the root of the kolla image repository at `2024.1-eom`) are [CODE]. Other image-side
statements in the sheets are **NOT AVAILABLE**. See [Kolla images](../../concepts/kolla-images.md).

**Context the sheets do not repeat.** The Ussuri sheets were written before the Ansible source was read for looped
tasks, and this still applies in ansible-core 2.16.20 [CODE]: when any item changes, Ansible notifies the handlers of
*every* executed loop item. Every executed item carries the task's `notify`
(`lib/ansible/executor/task_executor.py:819-820`),
an item whose `when` is false returns before it is set (`:483-484`), the task counts as changed when any item changed
(`:124-130`), and the strategy then notifies the handlers named by each item
(`lib/ansible/plugins/strategy/__init__.py:655-661`). Wherever a sheet says "restarts container X if its config
changed", read it as "restarts **all containers of that role on that host** if any of them changed" (see
[Tags §2.4][docs-03-loop-notify], [F1](../findings.md#f1)).

## Corrections

The Ussuri fact sheets were produced by parallel source-reading passes and spot-checked (MariaDB restart waves, glance
`log_bin_trust_function_creators`, the Docker restart gate, keepalived priority, compute-side memcached lists). Eleven
corrections applied to them. All are listed with their evidence, and their 2024.1 status, under [Verification and
errata](#verification-and-errata), above:

- **Fact sheets [A](a-infra-lb-ovn.md), [B](b-mariadb-rabbitmq-keystone.md) and [E](e-host-bootstrap-ops-playbooks.md)**
  (and any sentence elsewhere) stating that `docker stop` uses `docker_graceful_timeout` = 60 s were wrong for Ussuri,
  where the effective timeout was 10 s. **In 2024.1 the 60 s statement is right**, as in 2023.1, and
  `docker_client_timeout` is a working knob ([F3](../findings.md#f3)). A statement of 10 s, such as the one [fact sheet
  C](c-glance-placement-cinder-horizon-heat.md) made for Ussuri, does not hold for 2024.1.
- **[Fact sheet A](a-infra-lb-ovn.md)**, "no reload path anywhere": true for handlers, but `nova_scheduler` receives a
  `SIGHUP` on every `deploy`/`reconfigure` that runs the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag
  (or no tag) and whose `--limit` includes the `nova-scheduler` hosts (`nova.yml:152-172`). Still holds in 2024.1.
- **[Fact sheet B §3.10][sheet-b-310]**, memcached counts: in 2024.1, 23 roles use `memcache_secret_key`, and 27 embed
  the memcached host list (2023.1: 29 and 33; Ussuri: 35 and 38).
- **[Fact sheet A](a-infra-lb-ovn.md)**, `tags: always` on `import_role: haproxy-config` "in every `loadbalancer.yml`":
  in 2024.1 the import is of `loadbalancer-config`; 38 of 39 files do it directly; nova-cell reaches it through a chain
  of includes.
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, "Graceful stop" row: it stated 60 s, corrected to 10 s for
  Ussuri; 60 s is the 2023.1 and 2024.1 value ([F3](../findings.md#f3)).
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, Erlang cookie: the kolla image writes `.erlang.cookie` only in the
  `KOLLA_BOOTSTRAP` container, which runs only when the RabbitMQ volume is created, not at every start (still so in
  2024.1, `roles/rabbitmq/tasks/bootstrap.yml:2-26`). The sheet's former claim of a partition during the rolling
  recreate rested on that wrong premise; the corrected behaviour is in the second rabbitmq row of [Known bugs and
  limitations](../../troubleshooting/known-bugs-and-limitations.md).
- **[Fact sheet C](c-glance-placement-cinder-horizon-heat.md)**, four image-side statements, checked against the kolla
  sources and still true in `2024.1-eom` ([F15](../findings.md#f15), [Q14](../../troubleshooting/open-questions.md#q14)
  and [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run),
  [§5.2](../../concepts/kolla-images.md#52-horizon-static-assets)):
  - Placement online data migrations also run on every deploy/reconfigure, inside `bootstrap_placement`, not only on
    upgrade.
  - The heat domain admin is created only when `heat_user_domain` is absent, so a changed password is not
    re-applied.
  - Horizon's collectstatic/compress is conditional (settings hash changed or missing, a plugin toggled, or
    `FORCE_GENERATE=yes`), not run on every start.
  - The glance bootstrap also runs `glance-manage db_load_metadefs`.
- **[Fact sheet E](e-host-bootstrap-ops-playbooks.md)**, "For every other command, `-e kolla_serial=...` works":
  `upgrade` overrides it like `reconfigure` does (`tools/kolla-ansible:522,531`); use `ANSIBLE_SERIAL`. Still holds in
  2024.1.

## Related

- [Technical findings](../findings.md) — [F3](../findings.md#f3), the stop timeout (not ignored since 2023.1),
  [F15](../findings.md#f15), what the bootstrap containers run per image, and [F16](../findings.md#f16), the changed
  systemd unit template
- [Kolla images](../../concepts/kolla-images.md) — the kolla image sources behind the image-side errata
- [Known bugs and limitations](../../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and
  bugs found in `2024.1-eom`, among them the corrected RabbitMQ behaviour
- [Tags §2.4](../../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify,
  the context the sheets do not repeat
- [What is not known](../../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic

[sheet-b-310]: b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates
[docs-03-loop-notify]: ../../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code
