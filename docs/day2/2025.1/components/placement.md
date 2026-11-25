---
title: Placement
description: Where the 2025.1 study covers Placement (role placement), from its uWSGI switch and reconfigure to what its bootstrap container runs, Nova and open points.
tags: [placement, reconfigure, one-shot, uwsgi, risk, dependencies, bugs, unknowns]
---

# Placement

This page is the starting point for Placement, the `placement` role: one container, `placement_api`
(`roles/placement/defaults/main.yml:2-31`), on the control nodes of the example inventory
(`inventory/multinode:167-168`, `inventory/multinode:494-495`), selected by the tag `placement` (`site.yml:591-604`).
`enable_placement` defaults to `enable_nova` or `enable_zun` (`group_vars/all.yml:956`). Its bootstrap container runs
the DB sync and the online data migrations on every deploy and reconfigure ([Component dependencies
§3](dependencies.md#3-control-plane-services)).

**Changed in 2025.1** [CODE]:
- **uWSGI instead of Apache:** `placement_wsgi_provider` defaults to `uwsgi` (`roles/placement/defaults/main.yml:156`).
  The container command becomes `uwsgi /etc/placement/placement-api-uwsgi.ini`
  (`roles/placement/templates/placement-api.json.j2:3`), the role renders `placement-api-uwsgi.ini` through the shared
  `service-uwsgi-config` role (`roles/placement/tasks/config.yml:76-92`) and skips the Apache virtual host
  (`roles/placement/tasks/config.yml:58-74`). On the first 2025.1 run the `config.json` and the new uWSGI file change,
  so `placement_api` restarts on every placement host. Setting `placement_wsgi_provider: apache` keeps the 2024.1
  Apache path.
- **Log files:** with uWSGI, `placement-api-error.log` and `placement-api-access.log` are no longer written (they come
  from the Apache virtual host, `roles/placement/templates/placement-api-wsgi.conf.j2:31-33`). The service logs to
  `/var/log/kolla/placement/placement-api.log` (`log_file`, `roles/placement/templates/placement.conf.j2:4`;
  `service_name` is the service key, `roles/placement/tasks/config.yml:46`) and uWSGI to `placement-api-uwsgi.log`
  in the same directory (`roles/service-uwsgi-config/defaults/main.yml:4-5`,
  `roles/service-uwsgi-config/templates/uwsgi.ini.j2:14`). fluentd still tails `/var/log/kolla/placement/*.log`
  (`roles/common/defaults/main.yml:193-194`).
- **No rolling reconfigure:** `kolla-ansible reconfigure` forces `kolla_serial=0`, so the placement play (`serial`
  from `kolla_serial`, `site.yml:596`) restarts every `placement_api` at once; a batched run is
  `kolla-ansible deploy -t placement -e kolla_serial=N` ([F19](../reference/findings.md#f19)).
- **Restarts:** the config tasks notify nothing, except the Apache virtual host task (`apache` provider only,
  `roles/placement/tasks/config.yml:73-74`); `check-containers.yml` imports `service-check-containers`
  (`roles/placement/tasks/check-containers.yml:2-3`), which restarts `placement_api` only when its configuration or
  definition changed. The handler has no `kolla_action != "config"` guard any more
  (`roles/placement/handlers/main.yml:2-14`). `kolla-ansible check` runs the `service-check` role
  (`roles/placement/tasks/check.yml:2-4`).
- **Endpoints:** `placement_internal_endpoint` and `placement_public_endpoint` are no longer defined in the role; they
  are in `group_vars/all.yml` (`group_vars/all.yml:654-655`), still built with `kolla_url`, and the public port is
  still `placement_api_public_port` (`group_vars/all.yml:659`).
- **HAProxy health checks:** both placement backends add `option httpchk GET /`
  (`roles/placement/defaults/main.yml:20-21,30-31`). A `-t placement` run renders them but no longer restarts HAProxy
  ([F18](../reference/findings.md#f18)).
- **Configuration text:** `www_authenticate_uri` is `keystone_public_url` and `memcache_security_strategy` is a
  variable (`roles/placement/templates/placement.conf.j2:29,40`); `placement.conf` still has no messaging section, so
  the queue settings of [F17](../reference/findings.md#f17) do not reach it. `placement_copy_certs` drives the CA copy
  (`roles/placement/defaults/main.yml:151`); the image name takes `docker_image_name_prefix`
  (`roles/placement/defaults/main.yml:66`).
- **Still holds:** the deploy flow register → clone (if) → config → check-containers → bootstrap → flush
  (`roles/placement/tasks/deploy.yml:2-14`); the bootstrap container runs `db sync` and `online_data_migrations`
  (kolla `docker/placement/placement-api/extend_start.sh:5-9`; the kolla `docker/placement` directory only gains a
  `kolla_patch_sources()` call).

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Command quick lookup by tag](../operations/command-quick-lookup.md)

### Impact and risk

- **What the tag executes (`placement`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §2](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#2-placement)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `placement-api`),
  [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `deploy -e kolla_serial=N` (`reconfigure` forces `kolla_serial=0`, [F19](../reference/findings.md#f19)). Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [fact sheet C §2.8][sheet-c-28]: rotating `placement_keystone_password` needs a reconfigure of placement and nova (all
  computes) and neutron; cyborg also renders it, when enabled (`enable_cyborg`, default `no`) [CODE]
  (`roles/placement/templates/placement.conf.j2:36`, `roles/nova/templates/nova.conf.j2:184`,
  `roles/nova-cell/templates/nova.conf.j2:228`, `roles/neutron/templates/neutron.conf.j2:189`,
  `roles/cyborg/templates/cyborg.conf.j2:38`; `group_vars/all.yml:876`). No other template under `ansible/roles`
  renders it (grep).
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `--skip-tags haproxy` when you don't
  intend to change frontends; in 2025.1 a `-t placement` run renders the frontends without restarting HAProxy, so they
  apply at the next `-t haproxy` run ([F18](../reference/findings.md#f18)).
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`)
  ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts; raise
    `docker_graceful_timeout` if needed.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible genconfig -t <svc>`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, the API
    answers through the VIP and the container start times show which hosts restarted; HAProxy no longer restarts on a
  service tag ([F18](../reference/findings.md#f18)). For Placement with uWSGI, look for errors in `placement-api.log`
  and `placement-api-uwsgi.log`; `placement-api-error.log` is only written with the `apache` provider (above).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `site.yml`: placement
  haproxy include lacks `when: enable_placement` (`site.yml:248-251`). Status: still holds in 2025.1 [CODE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: Placement's `KOLLA_BOOTSTRAP` runs
  `db sync` + `online_data_migrations` on every deploy/reconfigure (`roles/placement/tasks/bootstrap_service.yml:10-12`,
  `roles/placement/tasks/deploy.yml:11`, `roles/placement/tasks/bootstrap.yml:38`; kolla
  `docker/placement/placement-api/extend_start.sh:5-9`). The kolla `docker/placement` directory differs from 2024.1
  only by a `kolla_patch_sources()` call in each Dockerfile (diff of the two trees).
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Placement's
  `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure [CODE].
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE]. For Placement, `reconfigure.yml` is an
  import of `deploy.yml` (`roles/placement/tasks/reconfigure.yml:2`).
- [What is not known](../troubleshooting/what-is-not-known.md#running-vms-and-compute-hosts), row on upstream Nova
  behaviour when a dependency is missing: for Placement, the sources do not establish whether scheduling stops while it
  restarts.
- [Nova deep dive §3](nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate), item 4: Placement serves the
  scheduler's allocation candidates and nova-compute's resource-provider updates; [NOT AVAILABLE] whether scheduling
  stops and computes log errors without it.
- [fact sheet C §2.8][sheet-c-28], "Operational notes and the relation to nova", three points: consumers authenticate as
  the placement user (`placement_keystone_user`, `group_vars/all.yml:975`; e.g.
  `roles/nova/templates/nova.conf.j2:183-184`); NOT AVAILABLE (upstream nova): how scheduling and the nova-compute
  resource tracker periodic task behave during a placement-api outage or restart; the upgrade db sync and online data
  migrations run while the old placement-api is still serving.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 6: Placement's online data migrations run on
  every deploy/reconfigure, inside `bootstrap_placement`, and twice on upgrade (`bootstrap_placement` with
  `KOLLA_BOOTSTRAP`, then again with `KOLLA_OSM` after the handler flush, `roles/placement/tasks/upgrade.yml:11-34`); a
  tag change applied with `deploy` therefore runs them [CODE].

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py placement -->

| Item | Value |
|---|---|
| Play | site.yml:591 |
| Tags | placement |
| Play host patterns | placement-api |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `placement_api` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → clone (if) → config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `migrate-db.rc.j2`, `placement-api-wsgi.conf.j2`, `placement-api.json.j2`, `placement.conf.j2` |
| Handlers (definition order) | Restart placement-api container |
| Key variables | `enable_placement` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as placement, with the risks and the verification
- [Nova](nova.md) — the scheduler and nova-compute use Placement
- [Nova deep dive §3](nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate) — Placement among what must be
  available before Nova can operate
- [Neutron](neutron.md) — one of the consumers that authenticate as the placement user
- [Update container images §4](../operations/update-container-images.md#4-risks) — a tag change applied with `deploy`
  runs no online data migrations, except Placement's
- [Component dependencies §6](dependencies.md#6-deployment-order-vs-runtime-dependency) — Placement is deployed before
  Nova
- [Apply common changes](../operations/apply-common-changes.md) — the fluentd input list, which includes placement,
  belongs to the `common` role
- [Components](index.md) — the other component pages

[sheet-c-28]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#28-operational-notes-and-the-relation-to-nova
