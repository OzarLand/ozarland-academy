---
title: Heat
description: Where the 2024.1 study covers Heat (role heat), from the single-service reconfigure and heat-engine restarts to the domain admin password bug and open points.
tags: [heat, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Heat

This page is the starting point for Heat, the `heat` role: the containers `heat_api`, `heat_api_cfn` and `heat_engine`
(`roles/heat/defaults/main.yml:4`, `roles/heat/defaults/main.yml:28`, `roles/heat/defaults/main.yml:52`), on the
control nodes of the example inventory (`inventory/multinode:128-129`, `inventory/multinode:350-357`), selected by the
tag `heat` (`site.yml:724-738`). A changed `heat_domain_admin_password` reaches `heat.conf` but is never applied in
Keystone (`roles/heat/templates/heat.conf.j2:12`, kolla `docker/heat/heat-api/extend_start.sh:10-14`; still holds in
2024.1; [Component dependencies §3](dependencies.md#3-control-plane-services)). The lists below say where the study
covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays
open; the service card follows them.

## What changed in 2024.1

- **Container module renamed** [CODE]: the three restart handlers, the check of the containers and the bootstrap
  container now use `kolla_container` instead of `kolla_docker`, with the same actions
  (`roles/heat/handlers/main.yml:2-48`, `roles/heat/tasks/check-containers.yml:2-5`,
  `roles/heat/tasks/bootstrap_service.yml:6-7`). The handlers are the same three, in the same order, and still skip
  `kolla_action == "config"` (`roles/heat/handlers/main.yml:15-16`).
- **Public URLs and the external frontends** [CODE]: the endpoints are built with the `kolla_url` filter
  (`roles/heat/defaults/main.yml:178-184`). The public ones use `heat_api_public_port` and `heat_api_cfn_public_port`,
  which become 443 or 80 with `haproxy_single_external_frontend` (default `false`) and otherwise stay 8004 and 8000
  (`group_vars/all.yml:412-419`, `group_vars/all.yml:931-932`). The two external HAProxy entries now carry
  `external_fqdn` and the public port (`roles/heat/defaults/main.yml:23-24`, `roles/heat/defaults/main.yml:47-48`).
  `heat.conf` builds `heat_metadata_server_url` and `heat_waitcondition_server_url` from the public CFN base endpoint
  (`roles/heat/templates/heat.conf.j2:6-7`), so turning the single external frontend on changes `heat.conf` on every
  heat host, and the config task then notifies the restart of each heat container
  (`roles/heat/tasks/config.yml:51-69`).
- **New messaging options in `heat.conf`** [CODE]: with the default quorum queues (`group_vars/all.yml:268`),
  `rabbit_quorum_queue = true` is rendered (`roles/heat/templates/heat.conf.j2:89-98`; see
  [F17](../reference/findings.md#f17)). With `om_enable_queue_manager` (default `false`, `group_vars/all.yml:269`) the
  three containers also mount `/dev/shm` (`roles/heat/defaults/main.yml:154`, `roles/heat/defaults/main.yml:161`,
  `roles/heat/defaults/main.yml:168`), and `heat.conf` gets `use_queue_manager`, a `processname` for `heat-api` and
  `heat-api-cfn` (`roles/heat/templates/heat.conf.j2:75-80`) and an `[oslo_concurrency]` lock path
  (`roles/heat/templates/heat.conf.j2:120-123`).
- **Config validation** [CODE]: `heat_config_validation` now points at `/heat/etc/heat/heat-config-generator.conf`
  (`roles/heat/defaults/main.yml:64`).
- **The play** [CODE]: it still takes `serial` from `kolla_serial`, default `0` (`site.yml:731`), and now also sets
  `max_fail_percentage`, default 100 (`site.yml:732-735`), which never stops the play early ([Controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
- **Still holds in 2024.1** [CODE]: the image side of the bootstrap is unchanged: kolla
  `docker/heat/heat-api/extend_start.sh`
  is the same file in both tags (`docker/heat/heat-api/extend_start.sh:5-17`). The only kolla change for Heat is that
  the base image now copies `heat_api_audit_map.conf` into `/etc/heat/` (kolla
  `docker/heat/heat-base/Dockerfile.j2:30`).

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)

No operation page gives a `reconfigure` command line for the `heat` tag. The scenario above describes
`kolla-ansible -t <svc> reconfigure` for an API service such as keystone, glance, cinder, heat or placement; its command
example is keystone ([Reconfigure a single service
§1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)). The `stop` example of [Stop and
destroy](../operations/stop-and-destroy.md) uses `-t heat`. For Heat, `reconfigure` runs `deploy.yml`
(`roles/heat/tasks/reconfigure.yml:2`): registration, config, check-containers, bootstrap, then the handlers
(`roles/heat/tasks/deploy.yml:2-15`) [CODE].

### Impact and risk

- **What the tag executes (`heat`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row `<svc>`;
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service
- **Risks:** [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet C §5](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#5-heat)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `heat-api`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [fact sheet C §5.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#58-operational-notes): with
  serial 0, every heat-engine restarts in the same handler flush on any heat.conf change; a memcached or rabbit
  membership change, a password rotation or an `openstack_service_workers` change is enough (`site.yml:731`;
  `roles/heat/templates/heat.conf.j2:12,16,19,46,52`, `roles/heat/defaults/main.yml:196`) [CODE]. Still holds in 2024.1.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2024.1 the stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:139`).
  Precautions: drain long operations before restarts; raise `docker_graceful_timeout` if needed (it reaches the unit on
  the next restart). The first 2024.1 check of a container whose unit 2023.1 wrote reports drift
  ([F16](../reference/findings.md#f16)).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, e.g.
  `heat` and `heat-cfn` for heat, each with an `internal` and a `public` endpoint
  (`roles/heat/defaults/main.yml:219-230`), the API answers through the VIP, the container start times show which hosts
  restarted, and the haproxy container's start time shows whether HAProxy restarted. If the public port changed (see
  [What changed in 2024.1](#what-changed-in-20241)), the public endpoints change too.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `heat`: `bootstrap_heat` creates
  `heat_user_domain`/`heat_domain_admin` only when the domain is absent: a changed `heat_domain_admin_password` reaches
  `heat.conf` but never Keystone. Status: [CODE], still holds in 2024.1 (kolla
  `docker/heat/heat-api/extend_start.sh:8-14`,
  `roles/heat/tasks/bootstrap_service.yml:22`); impact [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: Heat creates
  `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is
  never pushed to Keystone.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Heat's bootstrap container
  does not re-apply a changed `heat_domain_admin_password` to Keystone [CODE].
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": an Ussuri
  finding that no longer holds as written, in 2024.1 as in 2023.1. The role handlers pass `docker_common_options`,
  which carries `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and `client_timeout` (120 s)
  (`group_vars/all.yml:105`, `group_vars/all.yml:139`, `group_vars/all.yml:151-152`), and the container's systemd unit
  stops it with `<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:32`). On every
  restart, a service still running 60 s after SIGTERM is killed with its in-flight work (heat-engine, cinder copies,
  glance uploads); the 10 s value is only the fallback when no `graceful_timeout` is passed
  (`library/kolla_container.py:370-371`, `module_utils/kolla_docker_worker.py:417-419`,
  `module_utils/kolla_docker_worker.py:441-443`) [CODE] ([R24](../risk/risk-register.md#r24)).
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "Heat": the sources do not establish whether stack-domain operations fail authentication after a changed
  `heat_domain_admin_password`.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether xtrace writes one-shot secrets (the heat domain admin password among them) to the
  container's stderr.
- [fact sheet C §5.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#58-operational-notes),
  "Operational notes", four points: heat-engine restarts with stacks in progress (NOT AVAILABLE: upstream heat
  behaviour); with serial 0, every heat-engine restarts in the same handler flush on any heat.conf change; on upgrade
  the db sync runs while old engines are still active, and all engines restart together after it (2024.1, unchanged:
  config, check-containers, then `bootstrap_service.yml`, then the flush of handlers, `roles/heat/tasks/upgrade.yml:1-9`
  [CODE]); Heat does not touch compute hosts.
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list), items 8 and
  10: NOT AVAILABLE: heat-engine restart with `CREATE_IN_PROGRESS` stacks: final state and recovery steps; how heat
  behaves after `heat_domain_admin_password` changes, when `heat.conf` gets the new value but Keystone keeps the old
  one.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 7: a changed `heat_domain_admin_password`
  never reaches Keystone [CODE]; [NOT AVAILABLE] whether stack-domain operations then fail authentication.
- The effect on running stacks or on instances of a changed `heat_metadata_server_url` or
  `heat_waitcondition_server_url` (when the public CFN port changes) is [NOT AVAILABLE]: the sources only show the new
  value rendered into `heat.conf` (`roles/heat/templates/heat.conf.j2:6-7`).

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py heat -->

| Item | Value |
|---|---|
| Play | site.yml:724 |
| Tags | heat |
| Play host patterns | heat-api, heat-api-cfn, heat-engine |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `heat_api`, `heat_api_cfn`, `heat_engine` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `heat-api-cfn.json.j2`, `heat-api.json.j2`, `heat-engine.json.j2`, `heat.conf.j2`, `wsgi-heat-api-cfn.conf.j2`, `wsgi-heat-api.conf.j2` |
| Handlers (definition order) | Restart heat-api container; Restart heat-api-cfn container; Restart heat-engine container |
| Key variables | `enable_heat`, `heat_*_external_fqdn` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as heat, with the risks and the verification
- [Keystone](keystone.md) — a changed `heat_domain_admin_password` reaches `heat.conf` but never Keystone
- [Stop and destroy](../operations/stop-and-destroy.md) — the `stop` command line, whose example uses `-t heat`
- [R24](../risk/risk-register.md#r24) — heat-engine is one of the services named for the kill 60 s
  (`docker_graceful_timeout`) after SIGTERM
- [RabbitMQ](rabbitmq.md) — quorum queues on by default in 2024.1, rendered into `heat.conf`
- [Component dependencies §6](dependencies.md#6-deployment-order-vs-runtime-dependency) — Heat, Horizon and Octavia come
  after Nova and Neutron in the deployment order
- [Components](index.md) — the other component pages
