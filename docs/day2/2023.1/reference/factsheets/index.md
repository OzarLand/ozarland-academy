---
title: Per-role fact sheets
description: Five per-role fact sheets, first read from ussuri-eol and re-studied against 2023.1-eol, how they were checked, and the eleven corrections.
tags: [evidence, haproxy, keepalived, loadbalancer, memcached, chrony, ovn, mariadb, rabbitmq, keystone, glance, placement, cinder, horizon, heat, barbican, octavia, swift, manila, bootstrap-servers, prechecks, destroy]
---

# Per-role fact sheets

Five fact sheets first produced by systematic source reading of `ussuri-eol`, then re-studied against `2023.1-eol`:
each Ussuri citation was looked up in the 2023.1 sources and each statement re-checked there. Every **FACT** carries a
`path:line` reference relative to the kolla-ansible repository root, the kolla image repository (kolla `docker/...`),
ansible-collection-kolla (`ansible-collection-kolla roles/...`) or the Ansible source (ansible-core 2.14.18
`lib/ansible/...`). Anything these sources do not establish is labelled **NOT AVAILABLE**.

| Sheet | Scope |
|---|---|
| [A — infra / load balancing / OVN](a-infra-lb-ovn.md) | `loadbalancer` (haproxy, keepalived and proxysql; the Ussuri `haproxy` role, which no longer exists), the 44 per-service `loadbalancer.yml` includes, `loadbalancer-config`, `haproxy-config`, `proxysql-config`, `memcached`, `chrony` (no role in 2023.1), `ovn-controller` and `ovn-db` (the Ussuri `ovn` role), `ovs-dpdk`, `service-cert-copy`, `certificates.yml` |
| [B — MariaDB / RabbitMQ / Keystone](b-mariadb-rabbitmq-keystone.md) | Galera bootstrap/recovery/backup and rolling restart; RabbitMQ (incl. outward); Keystone fernet keys and runtime coupling |
| [C — Glance / Placement / Cinder / Horizon / Heat](c-glance-placement-cinder-horizon-heat.md) | per-role flow, bootstrap on reconfigure, dependencies, restart impact |
| [D — Barbican / Octavia / Swift / Manila + compute-side roles](d-barbican-octavia-swift-manila-compute-roles.md) | control-plane roles and every role that places containers on compute hosts; templates embedding host lists |
| [E — host bootstrap and operational playbooks](e-host-bootstrap-ops-playbooks.md) | `bootstrap-servers` (in 2023.1 the ansible-collection-kolla roles `baremetal`, `docker`, `etc_hosts` and others: Docker restart conditions, `/etc/hosts`), prechecks, destroy, prune-images, fact gathering, CLI, tuning docs |

The roles named above as gone are shown by the 2023.1 tree [CODE]: `ansible/roles/` has no `haproxy`, `chrony` or `ovn`
directory, and has `loadbalancer`, `proxysql-config`, `hacluster`, `ovn-controller` and `ovn-db`; `kolla-host.yml:4-10`
applies `openstack.kolla.baremetal`.

To go from a service or a tag to the right sheet section, use the [service index](../../components/index.md) and the
[tag index](../../risk/tag-index.md).

> [!NOTE]
> **Key answers**
>
> - **Eleven corrections to the Ussuri fact sheets**, each restated for 2023.1 below ([Corrections](#corrections)).
> - **The one with the widest effect is reversed in 2023.1:** `docker stop` now does use `docker_graceful_timeout`
>   (60 s), through each container's systemd unit; the Ussuri effective timeout of 10 s no longer applies
>   ([F3](../findings.md#f3)).

## Verification and errata

How the sheets were checked:

- **Spot checks against the source.** The five Ussuri spot checks, re-read in 2023.1 [CODE]:
  - MariaDB restart waves `index % 4`: **gone in 2023.1**. The handlers now only sort hosts into groups
    (`mariadb_bootstrap_restart`, `mariadb_restart`, `mariadb_start`; `roles/mariadb/handlers/main.yml:51-73`), and
    separate plays restart them with `serial: "33%"` (`mariadb.yml:14-40`); no `% 4` remains in the role or the
    playbook;
  - glance `log_bin_trust_function_creators` toggle: still there
    (`roles/glance/tasks/bootstrap_service.yml:2,12,39,49`);
  - Docker restart gate in `bootstrap-servers`: moved to ansible-collection-kolla. `daemon.json` and the registry CA
    notify `Restart docker` (ansible-collection-kolla `roles/docker/tasks/config.yml:36-47,99-108`), which restarts the
    daemon, or reloads it when `docker_systemd_reload` is set (default `false`)
    (`roles/docker/handlers/main.yml:2-15`, `roles/docker/defaults/main.yml:63`);
  - keepalived priority from inventory index: still there, now in the loadbalancer role
    (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`);
  - compute-side memcached lists: still there (`roles/ceilometer/templates/ceilometer.conf.j2:59`).
- **Ansible behaviours** that the sheets rely on are cited to the ansible-core 2.14.18 source where it shows them, and
  are marked NOT AVAILABLE where it does not.

**Erratum (sheets A, B and E, and any statement that `docker stop` honours `docker_graceful_timeout: 60`).**
**Ussuri:** the effective stop timeout of every `kolla_docker` stop/restart was **10 s**, because the argument spec set
`default=10` and a non-`None` module parameter overrode `common_options`. **2023.1: the erratum no longer applies**
[CODE]. `graceful_timeout` and `client_timeout` are declared without a default (`library/kolla_docker.py:303,325`), so
the merge takes the `common_options` values (`:351-382`): `docker_graceful_timeout: 60` and `docker_client_timeout:
120` (`group_vars/all.yml:105,140,152-153`). Containers other than one-shots run under a systemd unit
`kolla-<name>-container.service` whose `ExecStop` is `docker stop <name> -t <graceful_timeout>`
(`module_utils/kolla_systemd_worker.py:20-39,63-73`); a container without a unit file is stopped by the Docker client
with the same timeout, 10 s only when none is passed (`module_utils/kolla_docker_worker.py:436-452`).
`docker_client_timeout` is a working knob too: it is the Docker client timeout
(`module_utils/kolla_docker_worker.py:38`)
and the time the module waits for a unit to reach its state (`module_utils/kolla_systemd_worker.py:59,98,107`). A sheet
statement of 60 s therefore matches 2023.1, and one of 10 s describes Ussuri only ([F3](../findings.md#f3),
[R24](../../risk/risk-register.md#r24)).

**Erratum (sheet A, "There is no reload path anywhere in scope").** Still holds in 2023.1 [CODE]. It is true for the
handler path: every handler stops and starts or recreates its container, and `kolla_docker` has no reload action
(`library/kolla_docker.py:263-278`). Outside the handlers, Kolla sends one signal: the "Refresh nova scheduler cell
cache" play sends `SIGHUP` to `nova_scheduler` on the nova-scheduler hosts. It does so on `deploy` and `reconfigure`
runs that select the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag, or no tag (`nova.yml:140-156`,
`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`).

**Erratum (sheet B [§3.10][sheet-b-310], memcached counts).** **Ussuri:** 35 roles had `memcache_secret_key` in their
templates, 37 had `memcache_servers`/`memcached_servers`, and 38 embedded the memcached host list (37 template loops,
plus monasca's `monasca_memcached_servers`). **2023.1** [CODE, `grep` across `roles/*/templates`]: **29** roles have
`memcache_secret_key`, **32** have `memcache_servers`/`memcached_servers`, and **33** embed the memcached host list, all
by looping over `groups['memcached']` in their templates (this includes horizon, whose `CACHES.LOCATION` uses the loop,
`roles/horizon/templates/local_settings.j2:177-182`). The monasca role keeps only `defaults/` and `tasks/` and no
longer builds a memcached list. The list still includes `neutron.conf` (`roles/neutron/templates/neutron.conf.j2:125`),
which the neutron agents on compute hosts also read, so a memcached membership change reaches computes.

**Erratum (sheet A, "`tags: always` on the `import_role: haproxy-config` in every `loadbalancer.yml`").** In 2023.1
there are 44 `loadbalancer.yml` files, and each imports `loadbalancer-config` (not `haproxy-config`) with
`tags: always`; `loadbalancer-config` then imports `haproxy-config` and `proxysql-config` under conditions
(`roles/loadbalancer-config/tasks/main.yml:2-8`). 43 do it directly (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`;
ceph-rgw writes `role:` instead of `name:`, `roles/ceph-rgw/tasks/loadbalancer.yml:2-7`).
`roles/nova-cell/tasks/loadbalancer.yml` reaches it through a chain: `import_tasks: proxy_loadbalancer.yml`, then a
looped `include_tasks: cell_proxy_loadbalancer.yml`, then `import_role: loadbalancer-config`
(`roles/nova-cell/tasks/cell_proxy_loadbalancer.yml:3-12`), with `tags: always` at every level. The effect is the same
[CODE] ([Tags §2.3](../../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)).

**Erratum (image-side statements, kolla read later).** The kolla image sources were read after the Ussuri sheets were
written. Re-read in kolla `2023.1-eol` [CODE]:
- sheet A: keepalived's `/check_alive.sh` does query the haproxy stats socket (kolla
  `docker/keepalived/check_alive.sh:37`). The haproxy image ships a reload helper (kolla
  `docker/haproxy/haproxy/ensure_latest_config.sh:5-12`) that no file under kolla-ansible 2023.1 `ansible/` calls;
- sheet B: the broker's `.erlang.cookie` file is written only by the RabbitMQ bootstrap container, never on a normal
  broker start (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`; the image moved from `docker/rabbitmq/`);
- sheet C: the placement bootstrap container also runs `db online_data_migrations`, on every deploy and reconfigure
  (kolla `docker/placement/placement-api/extend_start.sh:5-9`). The glance bootstrap adds `db_load_metadefs` (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`). The heat bootstrap creates the heat domain and user only when the
  domain is absent (kolla `docker/heat/heat-api/extend_start.sh:5-17`). Horizon runs `collectstatic` only when its
  settings hash is missing or differs, a dashboard plugin is added or removed, or `FORCE_GENERATE=yes` (kolla
  `docker/horizon/extend_start.sh:32-46,248-293`;
  [Kolla images §5.2](../../concepts/kolla-images.md#52-horizon-static-assets));
- sheet D: swift config and rings are copied into a container only at its start (kolla `docker/base/start.sh:11`,
  `docker/base/set_configs.py:535-551`). Only `swift_rsyncd` fixes `/srv/node` ownership at start (kolla
  `docker/swift/swift-rsyncd/extend_start.sh:3`).

In the same Ussuri pass, sheet E [§11](e-host-bootstrap-ops-playbooks.md#11-toolskolla-ansible-cli) was corrected: like
`reconfigure`, `upgrade` overrides a user `-e kolla_serial`. This still holds in 2023.1 [CODE]: a user `-e` is added to
`EXTRA_OPTS` while the options are parsed (`tools/kolla-ansible:360-361`), and `upgrade` and `reconfigure` then append
`-e kolla_serial=${ANSIBLE_SERIAL}` after it (`:508`, `:517`; command line at `:587`). Statements that cite a kolla path
(kolla `docker/...`, relative to the root of the kolla image repository at `2023.1-eol`) are [CODE]. Other image-side
statements in the sheets are **NOT AVAILABLE**. See [Kolla images](../../concepts/kolla-images.md).

**Context the sheets do not repeat.** The Ussuri sheets were written before the Ansible source was read for looped
tasks, and this still applies in ansible-core 2.14.18 [CODE]: when any item changes, Ansible notifies the handlers of
*every* executed loop item. Every executed item carries the task's `notify`
(`lib/ansible/executor/task_executor.py:804-805`),
skipped items return before it is set (`:453-455`), the task counts as changed when any item changed (`:124-128`), and
the strategy then notifies the handlers named by each item (`lib/ansible/plugins/strategy/__init__.py:614-621`).
Wherever a sheet says "restarts container X if its config changed", read it as "restarts **all containers of that role
on that host** if any of them changed" (see [Tags §2.4][docs-03-loop-notify]).

## Corrections

The Ussuri fact sheets were produced by parallel source-reading passes and spot-checked (MariaDB restart waves, glance
`log_bin_trust_function_creators`, the Docker restart gate, keepalived priority, compute-side memcached lists). Eleven
corrections applied to them. All are listed with their evidence, and their 2023.1 status, under [Verification and
errata](#verification-and-errata), above:

- **Fact sheets [A](a-infra-lb-ovn.md), [B](b-mariadb-rabbitmq-keystone.md) and [E](e-host-bootstrap-ops-playbooks.md)**
  (and any sentence elsewhere) stating that `docker stop` uses `docker_graceful_timeout` = 60 s were wrong for Ussuri,
  where the effective timeout was 10 s. **In 2023.1 the 60 s statement is right** and `docker_client_timeout` is a
  working knob ([F3](../findings.md#f3)). A statement of 10 s, such as the one [fact sheet
  C](c-glance-placement-cinder-horizon-heat.md) made for Ussuri, does not hold for 2023.1.
- **[Fact sheet A](a-infra-lb-ovn.md)**, "no reload path anywhere": true for handlers, but `nova_scheduler` receives a
  `SIGHUP` on every `deploy`/`reconfigure` that runs the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag
  (or no tag) and whose `--limit` includes the `nova-scheduler` hosts (`nova.yml:140-156`). Still holds in 2023.1.
- **[Fact sheet B §3.10][sheet-b-310]**, memcached counts: in 2023.1, 29 roles use `memcache_secret_key`, and 33 embed
  the memcached host list (Ussuri: 35 and 38).
- **[Fact sheet A](a-infra-lb-ovn.md)**, `tags: always` on `import_role: haproxy-config` "in every `loadbalancer.yml`":
  in 2023.1 the import is of `loadbalancer-config`; 43 of 44 files do it directly; nova-cell reaches it through a chain
  of includes.
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, "Graceful stop" row: it stated 60 s, corrected to 10 s for
  Ussuri; 60 s is the 2023.1 value ([F3](../findings.md#f3)).
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, Erlang cookie: the kolla image writes `.erlang.cookie` only in the
  `KOLLA_BOOTSTRAP` container, which runs only on a new volume, not at every start (still so in 2023.1,
  `roles/rabbitmq/tasks/bootstrap.yml:10-26`). The sheet's former claim of a partition during the rolling recreate
  rested on that wrong premise; the corrected behaviour is in the second rabbitmq row of [Known bugs and
  limitations](../../troubleshooting/known-bugs-and-limitations.md).
- **[Fact sheet C](c-glance-placement-cinder-horizon-heat.md)**, four image-side statements, checked against the kolla
  sources and still true in `2023.1-eol` ([F15](../findings.md#f15), [Q14](../../troubleshooting/open-questions.md#q14)
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
  `upgrade` overrides it like `reconfigure` does (`tools/kolla-ansible:508,517`); use `ANSIBLE_SERIAL`. Still holds in
  2023.1.

## Related

- [Technical findings](../findings.md) — [F3](../findings.md#f3), the stop timeout (no longer ignored in 2023.1), and
  [F15](../findings.md#f15), what the bootstrap containers run per image
- [Kolla images](../../concepts/kolla-images.md) — the kolla image sources behind the image-side errata
- [Known bugs and limitations](../../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and
  bugs found in `2023.1-eol`, among them the corrected RabbitMQ behaviour
- [Tags §2.4](../../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify,
  the context the sheets do not repeat
- [What is not known](../../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic

[sheet-b-310]: b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates
[docs-03-loop-notify]: ../../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code
