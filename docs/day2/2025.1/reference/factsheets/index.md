---
title: Per-role fact sheets
description: "Five per-role fact sheets, re-studied against 2025.1-eom, how they were checked, and the eleven corrections with their 2025.1 status."
tags: [evidence, haproxy, keepalived, loadbalancer, letsencrypt, memcached, valkey, ovn, mariadb, proxysql, rabbitmq, keystone, glance, placement, cinder, horizon, heat, barbican, octavia, swift, manila, bootstrap-servers, prechecks, destroy]
---

# Per-role fact sheets

Five fact sheets first produced by systematic source reading of `ussuri-eol`, re-studied against `2023.1-eol` and
`2024.1-eom`, and re-studied again against `2025.1-eom`: each 2024.1 statement was looked up in the 2025.1 sources and
re-checked there. Every **FACT** carries a `path:line` reference relative to the kolla-ansible repository root, the
kolla image repository (kolla `docker/...`), ansible-collection-kolla (`ansible-collection-kolla roles/...`) or the
Ansible source (ansible-core 2.18.20 `lib/ansible/...`). Anything these sources do not establish is labelled
**NOT AVAILABLE**. The 2025.1 trees read are kolla-ansible `2025.1-eom`, kolla `2025.1-eom` and
ansible-collection-kolla `2025.1-eom`.

| Sheet | Scope |
|---|---|
| [A — infra / load balancing / OVN](a-infra-lb-ovn.md) | `loadbalancer` (haproxy, keepalived, proxysql, `haproxy-ssh`), the 38 per-service `loadbalancer.yml` includes, `loadbalancer-config`, `haproxy-config`, `proxysql-config`, `letsencrypt`, `memcached`, `ovn-controller` and `ovn-db` (with the SB relays, on by default in 2025.1), `ovs-dpdk`, `service-cert-copy`, `certificates.yml` |
| [B — MariaDB / RabbitMQ / Keystone](b-mariadb-rabbitmq-keystone.md) | Galera bootstrap/recovery/backup and rolling restart (through ProxySQL, the default in 2025.1); RabbitMQ (quorum queues and stream fanout on by default); Keystone fernet keys and runtime coupling |
| [C — Glance / Placement / Cinder / Horizon / Heat](c-glance-placement-cinder-horizon-heat.md) | per-role flow, bootstrap on reconfigure, dependencies, restart impact |
| [D — Barbican / Octavia / Swift / Manila + compute-side roles](d-barbican-octavia-swift-manila-compute-roles.md) | control-plane roles (the Swift role is removed in 2025.1) and every role that places containers on compute hosts; templates embedding host lists |
| [E — host bootstrap and operational playbooks](e-host-bootstrap-ops-playbooks.md) | `bootstrap-servers` (the ansible-collection-kolla roles `baremetal`, `docker` or `podman`, `etc_hosts` and others: Docker restart conditions, `/etc/hosts`), prechecks, destroy, prune-images, fact gathering, the CLI (rewritten in Python in 2025.1), tuning docs |

The roles named above as removed or present are shown by the 2025.1 tree [CODE]: `ansible/roles/` has no `swift`
directory any more, and has `loadbalancer`, `proxysql-config`, `hacluster`, `letsencrypt`, `valkey`, `ovn-controller`
and `ovn-db`; `kolla-host.yml:4-14` applies `openstack.kolla.baremetal`, whose engine role is chosen from
`kolla_container_engine` (ansible-collection-kolla `roles/baremetal/defaults/main.yml:37`,
`roles/baremetal/tasks/install.yml:37-38`).

To go from a service or a tag to the right sheet section, use the [service index](../../components/index.md) and the
[tag index](../../risk/tag-index.md).

> [!NOTE]
> **Key answers**
>
> - **Eleven corrections to the Ussuri fact sheets**, each restated for 2025.1 below ([Corrections](#corrections)).
> - **The stop timeout is 60 s in 2025.1 too:** a stop uses `docker_graceful_timeout` (60 s), through each container's
>   systemd unit written by the `kolla_container` module; the Ussuri effective timeout of 10 s does not apply
>   ([F3](../findings.md#f3)). The unit text changed again in 2025.1 (it gains `PartOf=kolla.target`), which makes the
>   first 2025.1 check restart a container whose unit 2024.1 wrote ([F16](../findings.md#f16)).
> - **Changed in 2025.1:** the loop-notify context the sheets did not repeat no longer applies to Kolla's own
>   restarts ([Tags §2.4][docs-03-loop-notify]), and `upgrade` and `reconfigure` can no longer be batched at all
>   ([F19](../findings.md#f19)).

## Verification and errata

How the sheets were checked:

- **Spot checks against the source.** The five Ussuri spot checks, re-read in 2025.1 [CODE]:
  - MariaDB restart waves `index % 4`: **gone since 2023.1, still gone in 2025.1**. The handlers only sort hosts into
    groups (`mariadb_bootstrap_restart`, `mariadb_restart`, `mariadb_start`; `roles/mariadb/handlers/main.yml:54-75`),
    and separate plays restart them with `serial: "33%"` (`mariadb.yml:18-52`); no `% 4` remains in the role or the
    playbook. These plays set `max_fail_percentage`, default 100 (`mariadb.yml:25-28`), which never stops a play early
    ([Controlled batches](../../operations/controlled-batches.md));
  - glance `log_bin_trust_function_creators` toggle: still there
    (`roles/glance/tasks/bootstrap_service.yml:2,12,39,49`);
  - Docker restart gate in `bootstrap-servers`: still in ansible-collection-kolla. `daemon.json` and the registry CA
    notify `Restart docker` (ansible-collection-kolla `roles/docker/tasks/config.yml:9-53,138-148`), which restarts
    the daemon, or reloads it when `docker_systemd_reload` is set (default `false`)
    (ansible-collection-kolla `roles/docker/handlers/main.yml:10-15`, `roles/docker/defaults/main.yml:71`). A change
    to the systemd drop-in notifies `Reload docker service file`, which in turn notifies `Restart docker`
    (`roles/docker/tasks/config.yml:89-125`, `roles/docker/handlers/main.yml:2-8`). `daemon.json` can carry
    `docker_debug` (`roles/docker/tasks/config.yml:46`, default `false` at `roles/docker/defaults/main.yml:74`);
  - keepalived priority from inventory index: still there
    (`roles/loadbalancer/templates/keepalived/keepalived.conf.j2:15`);
  - compute-side memcached lists: still there (`roles/ceilometer/templates/ceilometer.conf.j2:60`).
- **Ansible behaviours** that the sheets rely on are cited to the ansible-core 2.18.20 source where it shows them, and
  are marked NOT AVAILABLE where it does not. ansible-core 2.16.20, used for 2024.1, was read for the 2024.1 study;
  no statement here says what changed inside ansible-core between the two versions beyond the lines cited.

**Erratum (sheets A, B and E, and any statement that `docker stop` honours `docker_graceful_timeout: 60`).**
**Ussuri:** the effective stop timeout of every `kolla_docker` stop/restart was **10 s**, because the argument spec set
`default=10` and a non-`None` module parameter overrode `common_options`. **2025.1: the erratum still does not apply**
[CODE], as in 2023.1 and 2024.1. `kolla_container`'s `graceful_timeout` and `client_timeout` are declared without a
default (`library/kolla_container.py:311,333`); the merge takes the `common_options` values and falls back to 10 and
120 only when those are absent (`:371-389`, fallback values at `:366-367`): `docker_graceful_timeout: 60` and
`docker_client_timeout: 120` (`group_vars/all.yml:114,148,160-161`). Containers other than one-shots run under a
systemd unit `kolla-<name>-container.service` whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
(`module_utils/kolla_systemd_worker.py:33`; the engine is `docker` by default, `group_vars/all.yml:100`); a container
without a unit file is stopped by the Docker client with the same timeout, 10 s only when none is passed
(`module_utils/kolla_docker_worker.py:428-440`). `docker_client_timeout` is a working knob too: it is the Docker client
timeout (`module_utils/kolla_docker_worker.py:34`) and the time the module waits for a unit to reach its state
(`module_utils/kolla_systemd_worker.py:65,104,113`). A sheet statement of 60 s therefore matches 2025.1, and one of
10 s describes Ussuri only ([F3](../findings.md#f3)).

**Erratum (sheet A, "There is no reload path anywhere in scope").** Still holds in 2025.1 [CODE]. It is true for the
handler path: every handler stops and starts or recreates its container, and `kolla_container` has no reload action
(`library/kolla_container.py:272-285`). Outside the handlers, Kolla sends one signal: the "Refresh nova scheduler cell
cache" play sends `SIGHUP` to `nova_scheduler` on the nova-scheduler hosts. It does so on `deploy` and `reconfigure`
runs that select the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag, or no tag (`nova.yml:152-172`,
`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`).

**Erratum (sheet B [§3.10][sheet-b-310], memcached counts).** **Ussuri:** 35 roles had `memcache_secret_key` in their
templates, 37 had `memcache_servers`/`memcached_servers`, and 38 embedded the memcached host list. **2023.1:** 29, 32
and 33. **2024.1:** 23, 26 and 27. **2025.1** [CODE, recursive `grep` across `roles/*/templates`]: **22** roles have
`memcache_secret_key`, **25** have `memcache_servers`/`memcached_servers`, and **26** embed the memcached host list, all
by looping over `groups['memcached']` in their templates; the one fewer in each count is the removed swift role. This
includes horizon, whose `CACHES['default']['LOCATION']` uses the loop when `horizon_backend_database` is off
(`roles/horizon/templates/_9998-kolla-settings.py.j2:19-21`). A 27th role, telegraf, names the group only to test
whether the host itself runs memcached (`roles/telegraf/templates/telegraf.conf.j2:54-56`). The list still includes
`neutron.conf` (`roles/neutron/templates/neutron.conf.j2:121`), which the neutron agents on compute hosts also read,
so a memcached membership change reaches computes ([Memcached](../../components/memcached.md)).

**Erratum (sheet A, "`tags: always` on the `import_role: haproxy-config` in every `loadbalancer.yml`").** In 2025.1
there are 38 `loadbalancer.yml` files (39 in 2024.1, the swift one is gone), and each imports `loadbalancer-config`
(not `haproxy-config`) with `tags: always`; `loadbalancer-config` then imports `haproxy-config` and `proxysql-config`
under conditions (`roles/loadbalancer-config/tasks/main.yml:2-8`; `enable_proxysql` is now `yes` by default,
`group_vars/all.yml:958`). 37 do it directly (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`; ceph-rgw writes
`role:` instead of `name:`, `roles/ceph-rgw/tasks/loadbalancer.yml:2-7`). `roles/nova-cell/tasks/loadbalancer.yml`
reaches it through a chain: `import_tasks: proxy_loadbalancer.yml`, then a looped
`include_tasks: cell_proxy_loadbalancer.yml` (`roles/nova-cell/tasks/proxy_loadbalancer.yml:5-6`), then
`import_role: loadbalancer-config` (`roles/nova-cell/tasks/cell_proxy_loadbalancer.yml:2-11`), with `tags: always` at
every level. The effect is the same [CODE]
([Tags §2.3](../../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)).

**Erratum (image-side statements, kolla read later).** The kolla image sources were read after the Ussuri sheets were
written. Re-read in kolla `2025.1-eom` [CODE]:
- sheet A: keepalived's `/check_alive.sh` runs every script under `/checks` and fails if one fails (kolla
  `docker/keepalived/check_alive.sh:9-33`), as in 2024.1. The haproxy socket query is a script that kolla-ansible
  renders into that directory (`roles/loadbalancer/templates/keepalived/check_alive_haproxy.sh.j2:6`,
  `roles/loadbalancer/tasks/config.yml:90-95`, mounted at `/checks` by
  `roles/loadbalancer/templates/keepalived/keepalived.json.j2:11-12`). The haproxy image still ships a reload helper
  (kolla `docker/haproxy/haproxy/ensure_latest_config.sh:5-12`) that no file under kolla-ansible 2025.1 `ansible/`
  calls;
- sheet B: the broker's `.erlang.cookie` file is written only by the RabbitMQ bootstrap container, never on a normal
  broker start (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`, identical to 2024.1);
- sheet C: the placement bootstrap container also runs `db online_data_migrations`, on every deploy and reconfigure
  (kolla `docker/placement/placement-api/extend_start.sh:5-9`). The glance bootstrap adds `db_load_metadefs` (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`). The heat bootstrap creates the heat domain and user only when the
  domain is absent (kolla `docker/heat/heat-api/extend_start.sh:5-17`). These three files are identical to 2024.1.
  Horizon runs `collectstatic` only when its settings hash is missing or differs, a dashboard plugin is added or
  removed, or `FORCE_GENERATE=yes` (kolla `docker/horizon/extend_start.sh:32-46,203-248`). **Changed in 2025.1:** the
  hash now also covers `/etc/openstack-dashboard/themes` (`:213`), and `compress` runs once instead of being
  retried up to five times (`:246`) ([Kolla images §5.2](../../concepts/kolla-images.md#52-horizon-static-assets));
- sheet D: the swift images are not deployed by 2025.1 kolla-ansible, whose swift role is removed (see
  [sheet D §3](d-barbican-octavia-swift-manila-compute-roles.md#3-swift)). Config files are still copied into a
  container only at its start (kolla `docker/base/start.sh:11`, `docker/base/set_configs.py:559-575`); what changed in
  those two files in 2025.1 is in [Kolla images](../../concepts/kolla-images.md).

In the same Ussuri pass, sheet E was corrected: like `reconfigure`, `upgrade` overrides a user `-e kolla_serial`.
**Changed in 2025.1** [CODE]: the `tools/kolla-ansible` shell script is gone, replaced by the Python CLI in
`kolla_ansible/cli/commands.py`. `ANSIBLE_SERIAL` is now a constant of that module with the value 0, not an
environment variable (`kolla_ansible/cli/commands.py:20-22`), and `Reconfigure` and `Upgrade` add
`kolla_serial=0` after the user's `-e` options (`:136`, `:278`), so the override remains and can no longer be
steered: both commands always run each play on all its hosts in one batch ([F19](../findings.md#f19),
[Repository architecture](../../concepts/repository-architecture.md)). Statements that cite a kolla path (kolla
`docker/...`, relative to the root of the kolla image repository at `2025.1-eom`) are [CODE]. Other image-side
statements in the sheets are **NOT AVAILABLE**. See [Kolla images](../../concepts/kolla-images.md).

**Context the sheets do not repeat, changed in 2025.1.** The Ussuri sheets were written before the Ansible source was
read for looped tasks. The Ansible behaviour is unchanged in ansible-core 2.18.20 [CODE]: every executed item carries
the task's `notify` (`lib/ansible/executor/task_executor.py:850-851`), an item whose `when` is false returns before it
is set (`:511-515`), the task counts as changed when any item changed (`:136-140`), and the strategy then saves the
notifications of every item (`lib/ansible/plugins/strategy/__init__.py:640-653`). In 2024.1 this meant that "restarts
container X if its config changed" had to be read as "restarts all containers of that role on that host". **In 2025.1
Kolla no longer relies on it:** the config tasks no longer notify, and `service-check-containers` notifies only the
containers whose comparison changed, so a sheet statement "restarts container X if its config changed" can be read
literally ([Tags §2.4][docs-03-loop-notify], [F1](../findings.md#f1)).

## Corrections

The Ussuri fact sheets were produced by parallel source-reading passes and spot-checked (MariaDB restart waves, glance
`log_bin_trust_function_creators`, the Docker restart gate, keepalived priority, compute-side memcached lists). Eleven
corrections applied to them. All are listed with their evidence, and their 2025.1 status, under [Verification and
errata](#verification-and-errata), above:

- **Fact sheets [A](a-infra-lb-ovn.md), [B](b-mariadb-rabbitmq-keystone.md) and [E](e-host-bootstrap-ops-playbooks.md)**
  (and any sentence elsewhere) stating that `docker stop` uses `docker_graceful_timeout` = 60 s were wrong for Ussuri,
  where the effective timeout was 10 s. **In 2025.1 the 60 s statement is right**, as in 2023.1 and 2024.1, and
  `docker_client_timeout` is a working knob ([F3](../findings.md#f3)).
- **[Fact sheet A](a-infra-lb-ovn.md)**, "no reload path anywhere": true for handlers, but `nova_scheduler` receives a
  `SIGHUP` on every `deploy`/`reconfigure` that runs the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag
  (or no tag) and whose `--limit` includes the `nova-scheduler` hosts (`nova.yml:152-172`). Still holds in 2025.1.
- **[Fact sheet B §3.10][sheet-b-310]**, memcached counts: in 2025.1, 22 roles use `memcache_secret_key`, and 26 embed
  the memcached host list (2024.1: 23 and 27; 2023.1: 29 and 33; Ussuri: 35 and 38).
- **[Fact sheet A](a-infra-lb-ovn.md)**, `tags: always` on `import_role: haproxy-config` "in every `loadbalancer.yml`":
  in 2025.1 the import is of `loadbalancer-config`; 37 of 38 files do it directly; nova-cell reaches it through a chain
  of includes.
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, "Graceful stop" row: it stated 60 s, corrected to 10 s for
  Ussuri; 60 s is the 2023.1, 2024.1 and 2025.1 value ([F3](../findings.md#f3)).
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, Erlang cookie: the kolla image writes `.erlang.cookie` only in the
  `KOLLA_BOOTSTRAP` container, which runs only when the RabbitMQ volume is created, not at every start (still so in
  2025.1). The sheet's former claim of a partition during the rolling recreate rested on that wrong premise; the
  corrected behaviour is in [Known bugs and limitations](../../troubleshooting/known-bugs-and-limitations.md).
- **[Fact sheet C](c-glance-placement-cinder-horizon-heat.md)**, four image-side statements, checked against the kolla
  sources and still true in `2025.1-eom` ([F15](../findings.md#f15), [Q14](../../troubleshooting/open-questions.md#q14)
  and [Kolla images §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run),
  [§5.2](../../concepts/kolla-images.md#52-horizon-static-assets)):
  - Placement online data migrations also run on every deploy/reconfigure, inside `bootstrap_placement`, not only on
    upgrade.
  - The heat domain admin is created only when `heat_user_domain` is absent, so a changed password is not
    re-applied.
  - Horizon's collectstatic/compress is conditional (settings hash changed or missing, a plugin toggled, or
    `FORCE_GENERATE=yes`), not run on every start; in 2025.1 the hash also covers the themes directory.
  - The glance bootstrap also runs `glance-manage db_load_metadefs`.
- **[Fact sheet E](e-host-bootstrap-ops-playbooks.md)**, "For every other command, `-e kolla_serial=...` works":
  `upgrade` overrides it like `reconfigure` does. **Changed in 2025.1:** both now force `kolla_serial=0` and
  `ANSIBLE_SERIAL` is no longer read from the environment (`kolla_ansible/cli/commands.py:20-22,136,278`); to batch,
  use `deploy -e kolla_serial=N`, which runs the same tasks ([F19](../findings.md#f19)).

## Related

- [Technical findings](../findings.md) — [F3](../findings.md#f3), the stop timeout (not ignored since 2023.1),
  [F15](../findings.md#f15), what the bootstrap containers run per image, [F16](../findings.md#f16), the changed
  systemd unit template, and [F19](../findings.md#f19), `reconfigure` and `upgrade` cannot be batched
- [Kolla images](../../concepts/kolla-images.md) — the kolla image sources behind the image-side errata
- [Known bugs and limitations](../../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and
  bugs found in `2025.1-eom`, among them the corrected RabbitMQ behaviour
- [Tags §2.4][docs-03-loop-notify] — loop-notify, and why it no longer drives Kolla's restarts in 2025.1
- [What is not known](../../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [2024.1 fact sheet index](../../../2024.1/reference/factsheets/) — the same corrections with their 2024.1 status

[sheet-b-310]: b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates
[docs-03-loop-notify]: ../../risk/tags.md#24-loop-notify-is-gone-in-20251-code
