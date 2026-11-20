---
title: Per-role fact sheets
description: Five per-role fact sheets read from the ussuri-eol sources, how they were checked, and the eleven corrections that apply to them.
tags: [evidence, haproxy, keepalived, memcached, chrony, ovn, mariadb, rabbitmq, keystone, glance, placement, cinder, horizon, heat, barbican, octavia, swift, manila, bootstrap-servers, prechecks, destroy]
---

# Per-role fact sheets

Five fact sheets produced by systematic source reading of `ussuri-eol`. Every **FACT** carries a `path:line`
reference relative to the kolla-ansible repository root, the kolla image repository (kolla `docker/...`) or the
Ansible source (ansible 2.9.27 `lib/ansible/...`). Anything these sources do not establish is labelled
**NOT AVAILABLE**.

| Sheet | Scope |
|---|---|
| [A — infra / load balancing / OVN](a-infra-lb-ovn.md) | `haproxy` (+ keepalived, the 49 per-service `loadbalancer.yml` includes), `haproxy-config`, `memcached`, `chrony`, `ovn`, `ovs-dpdk`, `service-cert-copy`, `certificates.yml` |
| [B — MariaDB / RabbitMQ / Keystone](b-mariadb-rabbitmq-keystone.md) | Galera bootstrap/recovery/backup and rolling restart; RabbitMQ (incl. outward); Keystone fernet keys and runtime coupling |
| [C — Glance / Placement / Cinder / Horizon / Heat](c-glance-placement-cinder-horizon-heat.md) | per-role flow, bootstrap on reconfigure, dependencies, restart impact |
| [D — Barbican / Octavia / Swift / Manila + compute-side roles](d-barbican-octavia-swift-manila-compute-roles.md) | control-plane roles and every role that places containers on compute hosts; templates embedding host lists |
| [E — host bootstrap and operational playbooks](e-host-bootstrap-ops-playbooks.md) | `bootstrap-servers` (Docker restart conditions, `/etc/hosts`), prechecks, destroy, prune-images, fact gathering, CLI, tuning docs |

To go from a service or a tag to the right sheet section, use the [service index](../../components/index.md) and the
[tag index](../../risk/tag-index.md).

> [!NOTE]
> **Key answers**
>
> - **Eleven corrections to the fact sheets.** The one with the widest effect: `docker stop` does not use
>   `docker_graceful_timeout` = 60 s; the effective timeout is 10 s ([Corrections](#corrections)).

## Verification and errata

How the sheets were checked:

- **Spot checks against the source, all confirmed:**
  - MariaDB restart waves `index % 4` (`roles/mariadb/handlers/main.yml:66-78`);
  - glance `log_bin_trust_function_creators` toggle (`roles/glance/tasks/bootstrap_service.yml:2,38`);
  - Docker restart gate in `bootstrap-servers` (`roles/baremetal/tasks/post-install.yml:231-237`);
  - keepalived priority from inventory index (`roles/haproxy/templates/keepalived.conf.j2:13`);
  - compute-side memcached lists (`roles/ceilometer/templates/ceilometer.conf.j2:55`).
- **Ansible behaviours** that the sheets rely on are cited to the Ansible 2.9.27 source where it shows them, and
  are marked NOT AVAILABLE where it does not.

**Erratum (sheets A, B and E, and any statement that `docker stop` honours `docker_graceful_timeout: 60`).** The
effective stop timeout of every `kolla_docker` stop/restart is **10 s**. In `kolla_docker.generate_module()`, a module
parameter that is not `None` overrides `common_options`, and `graceful_timeout` defaults to `10`. The code shows it: the
argument spec sets `default=10` (`ansible/library/kolla_docker.py:991`), the merge loop skips only `None` values
(`:1037-1047`), and `stop_container` and `restart_container` pass the value to `docker stop` (`:871-884,892-903`). Sheet
C states it correctly. Sheet A (common mechanics, [§1.8](a-infra-lb-ovn.md#18-operationally-notable-behaviour)), sheet
B's "Graceful stop" row and sheet E ([§2.4](e-host-bootstrap-ops-playbooks.md#24-blast-radius-of-a-restart),
[§13](e-host-bootstrap-ops-playbooks.md#13-day-2-and-scale-knobs-etckollaglobalsyml-and-ansiblegroup_varsallyml)) had
the same error and are now corrected. Sheet E's
[§13](e-host-bootstrap-ops-playbooks.md#13-day-2-and-scale-knobs-etckollaglobalsyml-and-ansiblegroup_varsallyml) also
listed `docker_client_timeout` as a working knob; the module ignores it the same way ([Repository architecture
§6](../../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)).

**Erratum (sheet A, "There is no reload path anywhere in scope").** This holds for the handler path: every
handler stops and starts or recreates its container, and `kolla_docker` has no reload action. Outside the handlers,
Kolla sends one signal: the "Refresh nova scheduler cell cache" play sends `SIGHUP` to `nova_scheduler` on the
nova-scheduler hosts. It does so on `deploy` and `reconfigure` runs that select the `nova`, `nova-api` or
`nova-refresh-scheduler-cell-cache` tag, or no tag (`ansible/nova.yml:140-156`,
`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`).

**Erratum (sheet B [§3.10][sheet-b-310], memcached counts).** In `ussuri-eol`, **35** roles have `memcache_secret_key`
in their templates, not 34, and **37** (not 36) have `memcache_servers`/`memcached_servers`. The memcached *host list*
is embedded by **38** roles:
- 37 loop over `groups['memcached']` in their templates (this includes horizon, whose `CACHES.LOCATION` uses the
  loop);
- monasca builds the list in `monasca_memcached_servers` (`roles/monasca/defaults/main.yml:127`).

The list includes `neutron.conf`, which the neutron agents on compute hosts also read, so a memcached membership
change reaches computes.

**Erratum (sheet A, "`tags: always` on the `import_role: haproxy-config` in every `loadbalancer.yml`").** This holds
for 48 of the 49 `loadbalancer.yml` files. `roles/nova-cell/tasks/loadbalancer.yml` does not import `haproxy-config`
itself. It reaches it through a chain: `import_tasks: proxy_loadbalancer.yml`, then `include_tasks:
cell_proxy_loadbalancer.yml`, then `import_role: haproxy-config`, with `tags: always` at every level. The effect is the
same.

**Erratum (image-side statements, kolla `ussuri-eol` read later).** The kolla image sources were read after the
sheets were written. The main changes, now made in the sheets, are:
- sheet A: keepalived's `/check_alive.sh` does query the haproxy stats socket (kolla
  `docker/keepalived/check_alive.sh:6`). The haproxy image ships a reload helper that kolla-ansible ussuri never calls
  (kolla `docker/haproxy/ensure_latest_config.sh:5-14`);
- sheet B: the broker's `.erlang.cookie` file is written only by the RabbitMQ bootstrap container, never on a
  normal broker start (kolla `docker/rabbitmq/extend_start.sh:7-18`);
- sheet C: the placement bootstrap container also runs `db online_data_migrations`, on every deploy and reconfigure
  (kolla `docker/placement/placement-api/extend_start.sh:5-9`). The glance bootstrap adds `db_load_metadefs` (kolla
  `docker/glance/glance-api/extend_start.sh:5-9`). The heat bootstrap creates the heat domain and user only when the
  domain is absent (kolla `docker/heat/heat-api/extend_start.sh:5-17`). Horizon runs `collectstatic` only when its
  settings hash is missing or differs, a dashboard plugin is added or removed, or `FORCE_GENERATE=yes` (kolla
  `docker/horizon/extend_start.sh:57-63,322-337,368-372`);
- sheet D: swift config and rings are copied into a container only at its start (kolla `docker/base/start.sh:8`,
  `docker/base/set_configs.py:391-393`). Only `swift_rsyncd` fixes `/srv/node` ownership at start (kolla
  `docker/swift/swift-rsyncd/extend_start.sh:3`).

In the same pass, sheet E [§11](e-host-bootstrap-ops-playbooks.md#11-toolskolla-ansible-cli) was corrected: like
`reconfigure`, `upgrade` overrides a user `-e kolla_serial` (`tools/kolla-ansible:430`). Sheets B and C also now cite
the kolla source for several image-side statements that were earlier only inferred and that it confirms, for example the
keystone, cinder and horizon bootstrap commands and glance's recursive chown of `/var/lib/glance`. Statements that cite
a kolla path (kolla `docker/...`, relative to the root of the kolla image repository at `ussuri-eol`) are [CODE]. Other
image-side statements in the sheets are **NOT AVAILABLE**. See [Kolla images](../../concepts/kolla-images.md).

**Context the sheets do not repeat.** The sheets were written before the Ansible 2.9 source was read for looped tasks:
when any item changes, Ansible notifies the handlers of *every* executed loop item. Every executed item carries the
task's `notify`, skipped items return before it is set, the task counts as changed when any item changed, and the
strategy then notifies the handlers named by each item (ansible 2.9.27
`lib/ansible/executor/task_executor.py:118-121,559,789-790`, `lib/ansible/plugins/strategy/__init__.py:609-623`).
Wherever a sheet says "restarts container X if its config changed", read it as "restarts **all containers of that role
on that host** if any of them changed" (see [Tags §2.4][docs-03-loop-notify]).

## Corrections

The fact sheets were produced by parallel source-reading passes and spot-checked (MariaDB restart waves, glance
`log_bin_trust_function_creators`, the Docker restart gate, keepalived priority, compute-side memcached lists: all
confirmed). Eleven corrections apply. All are listed with their evidence under [Verification and
errata](#verification-and-errata), above. In the list below, the first bullet (in sheets A, B and E) and the last four
bullets (eight corrections) were also made in the sheets themselves:

- **Fact sheets [A](a-infra-lb-ovn.md), [B](b-mariadb-rabbitmq-keystone.md) and [E](e-host-bootstrap-ops-playbooks.md)**
  (and any sentence elsewhere) stating that `docker stop` uses `docker_graceful_timeout` = 60 s are wrong. The effective
  timeout is **10 s** ([F3](../findings.md#f3)). Sheet E also listed `docker_client_timeout` as a working knob; it is
  ignored the same way. [Fact sheet C](c-glance-placement-cinder-horizon-heat.md) states this correctly. This is the
  correction with the widest effect.
- **[Fact sheet A](a-infra-lb-ovn.md)**, "no reload path anywhere": true for handlers, but `nova_scheduler` receives a
  `SIGHUP` on every `deploy`/`reconfigure` that runs the `nova`, `nova-api` or `nova-refresh-scheduler-cell-cache` tag
  (or no tag) and whose `--limit` includes the `nova-scheduler` hosts (`ansible/nova.yml:139-156`).
- **[Fact sheet B §3.10][sheet-b-310]**, memcached counts: 35 roles use `memcache_secret_key`, and 38 embed the
  memcached host list.
- **[Fact sheet A](a-infra-lb-ovn.md)**, `tags: always` on `import_role: haproxy-config` "in every `loadbalancer.yml`":
  48 of 49 files do it directly; nova-cell reaches it through a chain of includes.
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, "Graceful stop" row: it also stated 60 s; the sheet now states 10
  s ([F3](../findings.md#f3)).
- **[Fact sheet B](b-mariadb-rabbitmq-keystone.md)**, Erlang cookie: the kolla image writes `.erlang.cookie` only in the
  `KOLLA_BOOTSTRAP` container, which runs only on a new volume, not at every start. The sheet's former claim of a
  partition during the rolling recreate rested on that wrong premise; the corrected behaviour is in the second rabbitmq
  row of [Known bugs and limitations](../../troubleshooting/known-bugs-and-limitations.md).
- **[Fact sheet C](c-glance-placement-cinder-horizon-heat.md)**, four image-side statements, checked against the kolla
  `ussuri-eol` sources ([F15](../findings.md#f15), [Q14](../../troubleshooting/open-questions.md#q14) and [Kolla images
  §4](../../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run),
  [§5.2](../../concepts/kolla-images.md#52-horizon-static-assets)):
  - Placement online data migrations also run on every deploy/reconfigure, inside `bootstrap_placement`, not only on
    upgrade.
  - The heat domain admin is created only when `heat_user_domain` is absent, so a changed password is not
    re-applied.
  - Horizon's collectstatic/compress is conditional (settings hash changed or missing, a plugin toggled, or
    `FORCE_GENERATE=yes`), not run on every start.
  - The glance bootstrap also runs `glance-manage db_load_metadefs`.
- **[Fact sheet E](e-host-bootstrap-ops-playbooks.md)**, "For every other command, `-e kolla_serial=...` works":
  `upgrade` overrides it like `reconfigure` does (`tools/kolla-ansible:430`); use `ANSIBLE_SERIAL`.

## Related

- [Technical findings](../findings.md) — [F3](../findings.md#f3), the ignored stop timeout, and
  [F15](../findings.md#f15), what the bootstrap containers run per image
- [Kolla images](../../concepts/kolla-images.md) — the kolla image sources behind the image-side errata
- [Known bugs and limitations](../../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and
  bugs found in `ussuri-eol`, among them the corrected RabbitMQ behaviour
- [Tags §2.4](../../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify,
  the context the sheets do not repeat
- [What is not known](../../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic

[sheet-b-310]: b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates
[docs-03-loop-notify]: ../../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code
