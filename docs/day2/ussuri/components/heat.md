---
title: Heat
description: Where the study covers Heat (role heat), from the single-service reconfigure and heat-engine restarts to the domain admin password bug and open points.
tags: [heat, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Heat

This page is the starting point for Heat, the `heat` role: the containers `heat_api`, `heat_api_cfn` and `heat_engine`,
on the control nodes of the example inventory, selected by the tag `heat`. A changed `heat_domain_admin_password`
reaches `heat.conf` but is never applied in Keystone ([Component dependencies
§3](dependencies.md#3-control-plane-services)). The lists below say where the study covers how to operate it, its
impact, its dependencies and the evidence, what to check around a run and what stays open; the service card follows
them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)

No operation page gives a `reconfigure` command line for the `heat` tag. The scenario above describes
`kolla-ansible -t <svc> reconfigure` for an API service such as keystone, glance, cinder, heat or placement; its command
example is keystone ([Reconfigure a single service
§1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)). The `stop` example of [Stop and
destroy](../operations/stop-and-destroy.md) uses `-t heat`.

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
  membership change, a password rotation or an `openstack_service_workers` change is enough.
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), precautions for the effective container stop timeout of 10 s: drain long
  operations before restarts; patch `kolla_docker` or pass `graceful_timeout` if needed.
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, e.g.
  `heat` and `heat-cfn` for heat, the API answers through the VIP, the container start times show which hosts restarted,
  and `docker ps --filter name=haproxy` shows whether HAProxy restarted.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `heat`: `bootstrap_heat` creates
  `heat_user_domain`/`heat_domain_admin` only when the domain is absent: a changed `heat_domain_admin_password` reaches
  `heat.conf` but never Keystone. Status: [CODE]; impact [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: Heat creates
  `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is
  never pushed to Keystone.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Heat's bootstrap container
  does not re-apply a changed `heat_domain_admin_password` to Keystone [CODE].
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored" [CODE]: on
  every restart, a service still running 10 s after SIGTERM is SIGKILLed with its in-flight work (heat-engine, cinder
  copies, glance uploads).
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
  the db sync runs while old engines are still active, and all engines restart together after it; Heat does not touch
  compute hosts.
- [fact sheet C §8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#8-not-available-list), items 8 and
  10: NOT AVAILABLE: heat-engine restart with `CREATE_IN_PROGRESS` stacks: final state and recovery steps; how heat
  behaves after `heat_domain_admin_password` changes, when `heat.conf` gets the new value but Keystone keeps the old
  one.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 7: a changed `heat_domain_admin_password`
  never reaches Keystone [CODE]; [NOT AVAILABLE] whether stack-domain operations then fail authentication.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py heat -->

| Item | Value |
|---|---|
| Play | site.yml:793 |
| Tags | heat |
| Play host patterns | heat-api, heat-api-cfn, heat-engine |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `heat_api`, `heat_api_cfn`, `heat_engine` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → clone (if) → bootstrap → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, stop.yml, upgrade.yml |
| Templates | `heat-api-cfn.json.j2`, `heat-api.json.j2`, `heat-engine.json.j2`, `heat.conf.j2`, `wsgi-heat-api-cfn.conf.j2`, `wsgi-heat-api.conf.j2` |
| Handlers (definition order) | Restart heat-api container; Restart heat-api-cfn container; Restart heat-engine container |
| Key variables | `enable_heat`, `heat_*_external_fqdn` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — what `-t <svc> reconfigure` runs for an API
  service such as heat, with the risks and the verification
- [Keystone](keystone.md) — a changed `heat_domain_admin_password` reaches `heat.conf` but never Keystone
- [Stop and destroy](../operations/stop-and-destroy.md) — the `stop` command line, whose example uses `-t heat`
- [R24](../risk/risk-register.md#r24) — heat-engine is one of the services named for the SIGKILL 10 s after SIGTERM
- [Component dependencies §6](dependencies.md#6-deployment-order-vs-runtime-dependency) — Heat, Horizon and Octavia come
  after Nova and Neutron in the deployment order
- [Components](index.md) — the other component pages
