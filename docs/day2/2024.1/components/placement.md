---
title: Placement
description: Where the 2024.1 study covers Placement (role placement), from its reconfigure and what its bootstrap container runs to its relation to Nova and open points.
tags: [placement, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Placement

This page is the starting point for Placement, the `placement` role: one container, `placement_api`
(`roles/placement/defaults/main.yml:2-26`), on the control nodes of the example inventory
(`inventory/multinode:171-172`, `inventory/multinode:505-506`), selected by the tag `placement` (`site.yml:593-606`).
`enable_placement` defaults to `enable_nova` or `enable_zun` (`group_vars/all.yml:837`). Its bootstrap container runs
the DB sync and the online data migrations on every deploy and reconfigure ([Component dependencies
§3](dependencies.md#3-control-plane-services)). The role is unchanged since 2023.1 except for the module rename
(`kolla_docker` → `kolla_container`) and the few points listed below [CODE]. The lists below say where the study covers
how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the
service card follows them.

## What changed in 2024.1

- **Endpoints and the external frontend** [CODE]: `placement_internal_endpoint` and `placement_public_endpoint` are
  built with the `kolla_url` filter (`roles/placement/defaults/main.yml:92-93`), and the public one uses
  `placement_api_public_port`, which becomes 443 or 80 with the single external frontend option
  (`group_vars/all.yml:558`). The external HAProxy entry now takes `external_fqdn` and that port
  (`roles/placement/defaults/main.yml:19-26`). With the default (`haproxy_single_external_frontend` off) the port stays
  `8780` (`group_vars/all.yml:556`).
- **Apache error log file name** [CODE]: the WSGI virtual host writes its errors to `placement-api-error.log`
  (`roles/placement/templates/placement-api-wsgi.conf.j2:31`); 2023.1 wrote them to `placement-api.log`. The access log
  is still `placement-api-access.log` (`roles/placement/templates/placement-api-wsgi.conf.j2:33`).
- **fluentd now reads the placement logs** [CODE]: `placement` is in `fluentd_input_openstack_services`
  (`roles/common/defaults/main.yml:201-202`), so the global fluentd input tails `/var/log/kolla/placement/*.log`
  (`roles/common/templates/conf/input/00-global.conf.j2:5`); the 2023.1 list had no `placement` entry. This changes the
  fluentd config of the `common` role, not the placement container.
- **No RabbitMQ change applies** [CODE]: `placement.conf` has no messaging section
  (`roles/placement/templates/placement.conf.j2:1-55`), so the quorum-queue defaults of
  [F17](../reference/findings.md#f17) do not reach it.
- **Still holds in 2024.1** [CODE]: the single handler, skipped when `kolla_action` is `config`
  (`roles/placement/handlers/main.yml:2-16`); the deploy flow register → clone (if) → config → check-containers →
  bootstrap → flush (`roles/placement/tasks/deploy.yml:2-14`); the play still takes `serial` from `kolla_serial` and now
  also sets `max_fail_percentage`, default 100 (`site.yml:598-602`), which never stops the play early ([Controlled
  batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)). The first
  2024.1 check of a container whose unit 2023.1 wrote reports drift ([F16](../reference/findings.md#f16)).

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
  `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [fact sheet C §2.8][sheet-c-28]: rotating `placement_keystone_password` needs a reconfigure of placement and nova (all
  computes) and neutron; cyborg also renders it, when enabled (`enable_cyborg`, default `no`) [CODE]
  (`roles/placement/templates/placement.conf.j2:36`, `roles/nova/templates/nova.conf.j2:196`,
  `roles/nova-cell/templates/nova.conf.j2:238`, `roles/neutron/templates/neutron.conf.j2:200`,
  `roles/cyborg/templates/cyborg.conf.j2:38`; `group_vars/all.yml:762`). No other template under `ansible/roles`
  renders it (grep).
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2024.1 the stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:139`)
  ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts; raise
  `docker_graceful_timeout` if needed (it reaches the unit on the next restart).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, the API
  answers through the VIP, the container start times show which hosts restarted, and the haproxy container's start time
  shows whether HAProxy restarted. For Placement, look for Apache errors in `placement-api-error.log`, no longer in
  `placement-api.log` (above).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `site.yml`: placement
  haproxy include lacks `when: enable_placement` (`site.yml:248-251`). Status: still holds in 2024.1 [CODE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: Placement's `KOLLA_BOOTSTRAP` runs
  `db sync` + `online_data_migrations` on every deploy/reconfigure (`roles/placement/tasks/bootstrap_service.yml:10-12`,
  `roles/placement/tasks/deploy.yml:11`, `roles/placement/tasks/bootstrap.yml:38`; kolla
  `docker/placement/placement-api/extend_start.sh:5-9`). The kolla `docker/placement` directory is unchanged from
  2023.1 (diff of the two trees).
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
  the placement user (`placement_keystone_user`, `group_vars/all.yml:858`; e.g.
  `roles/nova/templates/nova.conf.j2:195-196`); NOT AVAILABLE (upstream nova): how scheduling and the nova-compute
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
| Play | site.yml:593 |
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
- [Apply common changes](../operations/apply-common-changes.md) — the fluentd input list, which now includes placement,
  belongs to the `common` role
- [Components](index.md) — the other component pages

[sheet-c-28]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#28-operational-notes-and-the-relation-to-nova
