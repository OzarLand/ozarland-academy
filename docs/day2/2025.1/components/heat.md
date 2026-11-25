---
title: Heat
description: Where the 2025.1 study covers Heat (role heat), from the single-service reconfigure and heat-engine restarts to the domain admin password bug and open points.
tags: [heat, reconfigure, one-shot, risk, dependencies, bugs, unknowns]
---

# Heat

This page is the starting point for Heat, the `heat` role: the containers `heat_api`, `heat_api_cfn` and `heat_engine`
(`roles/heat/defaults/main.yml:4`, `roles/heat/defaults/main.yml:32`, `roles/heat/defaults/main.yml:60`), on the
control nodes of the example inventory (`inventory/multinode:125-126`, `inventory/multinode:339-346`), selected by the
tag `heat` (`site.yml:722-736`). A changed `heat_domain_admin_password` reaches `heat.conf` but is never applied in
Keystone (`roles/heat/templates/heat.conf.j2:12`, kolla `docker/heat/heat-api/extend_start.sh:10-14`; still holds in
2025.1; [Component dependencies §3](dependencies.md#3-control-plane-services)).

**Changed in 2025.1** [CODE]:
- **Restarts:** the config tasks notify nothing; `check-containers.yml` imports `service-check-containers`
  (`roles/heat/tasks/check-containers.yml:2-3`), which restarts only the heat containers whose configuration or
  definition changed ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). A `heat.conf` change still
  reaches all three containers, since each has its own copy. The three handlers have no `kolla_action != "config"`
  guard any more (`roles/heat/handlers/main.yml:2-42`). New `check.yml` for `kolla-ansible check`.
- **No rolling reconfigure or upgrade through the CLI** ([F19](../reference/findings.md#f19)): every `heat_engine`
  restarts in the same handler flush; a batched reconfigure is `kolla-ansible deploy -t heat -e kolla_serial=N`.
- **`[volumes] backups_enabled`** follows `enable_cinder_backup` (`roles/heat/templates/heat.conf.j2:111-112`), so the
  first 2025.1 run changes `heat.conf`, and enabling or disabling cinder-backup later restarts the heat containers.
- **First-run changes:** the three containers always mount `/dev/shm` (`roles/heat/defaults/main.yml:162`,
  `roles/heat/defaults/main.yml:169`, `roles/heat/defaults/main.yml:176`) and are recreated; `use_queue_manager`, the
  `processname` and the quorum settings are always rendered (`roles/heat/templates/heat.conf.j2:75-89`;
  [F17](../reference/findings.md#f17)); `www_authenticate_uri` is `keystone_public_url` and
  `memcache_security_strategy` a variable (`roles/heat/templates/heat.conf.j2:33,44`).
- **Endpoints:** the URLs are composed from `heat_internal_base_endpoint`, `heat_public_base_endpoint` and the CFN base
  endpoints, now in `group_vars/all.yml` (`group_vars/all.yml:465-466`, `group_vars/all.yml:472-473`,
  `roles/heat/defaults/main.yml:186-190`); the release notes call the `heat-cfn` part a fix of its internal endpoint.
  With the defaults the URL text is the same as in 2024.1 (same FQDN, port and path).
- **Other:** the four HAProxy backends add `option httpchk` (`roles/heat/defaults/main.yml:20,30,48,58`), rendered by
  `-t heat` without restarting HAProxy ([F18](../reference/findings.md#f18)); `heat_copy_certs`
  (`roles/heat/defaults/main.yml:258`); the image names take `docker_image_name_prefix`; the heat-base image pins
  setuptools 81 (kolla `docker/heat/heat-base/Dockerfile.j2:26-30`).
- **Still holds:** the three handlers in the same order; `heat_metadata_server_url` and
  `heat_waitcondition_server_url` from the public CFN base endpoint (`roles/heat/templates/heat.conf.j2:6-7`); the
  image start script, identical to 2024.1's (kolla `docker/heat/heat-api/extend_start.sh:5-17`).

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

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
  `deploy -e kolla_serial=N` (`reconfigure` forces `kolla_serial=0`, [F19](../reference/findings.md#f19)). Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [fact sheet C §5.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#58-operational-notes): with
  serial 0 (always the case for `reconfigure` in 2025.1), every heat-engine restarts in the same handler flush on any heat.conf change; a memcached or rabbit
  membership change, a password rotation, an `openstack_service_workers` change or, new in 2025.1, a change of
  `enable_cinder_backup` is enough (`site.yml:729`;
  `roles/heat/templates/heat.conf.j2:12,16,19,46,52`, `roles/heat/defaults/main.yml:202`, `roles/heat/templates/heat.conf.j2:112`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `--skip-tags haproxy` when you don't
  intend to change frontends; a `-t heat` run renders the frontends without restarting HAProxy
  ([F18](../reference/findings.md#f18)).
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`).
    Precautions: drain long operations before restarts; raise `docker_graceful_timeout` if needed. The first 2025.1
  check of a container whose unit 2024.1 wrote reports drift ([F16](../reference/findings.md#f16)).
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible genconfig -t <svc>`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, e.g.
  `heat` and `heat-cfn` for heat, each with an `internal` and a `public` endpoint
    (`roles/heat/defaults/main.yml:224-236`), the API answers through the VIP and the container start times show which
  hosts restarted; HAProxy no longer restarts on a service tag ([F18](../reference/findings.md#f18)). If the public port
  changes (`haproxy_single_external_frontend`, `group_vars/all.yml:467-476`), the public endpoints change too.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `heat`: `bootstrap_heat` creates
  `heat_user_domain`/`heat_domain_admin` only when the domain is absent: a changed `heat_domain_admin_password` reaches
  `heat.conf` but never Keystone. Status: [CODE], still holds in 2025.1 (kolla
  `docker/heat/heat-api/extend_start.sh:8-14`,
  `roles/heat/tasks/bootstrap_service.yml:22`); impact [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: Heat creates
  `heat_user_domain`/`heat_domain_admin` only if the domain is absent, so a changed `heat_domain_admin_password` is
  never pushed to Keystone.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Heat's bootstrap container
  does not re-apply a changed `heat_domain_admin_password` to Keystone [CODE].
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": an Ussuri
  finding that no longer holds as written, in 2025.1 as in 2024.1. The role handlers pass `docker_common_options`,
  which carries `graceful_timeout: "{{ docker_graceful_timeout }}"` (60 s) and `client_timeout` (120 s)
  (`group_vars/all.yml:114`, `group_vars/all.yml:148`, `group_vars/all.yml:160-161`), and the container's systemd unit
  stops it with `<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:33`). On every
  restart, a service still running 60 s after SIGTERM is killed with its in-flight work (heat-engine, cinder copies,
  glance uploads); the 10 s value is only the fallback when no `graceful_timeout` is passed
  (`library/kolla_container.py:366-367`, `module_utils/kolla_docker_worker.py:428-430`,
  `module_utils/kolla_docker_worker.py:428-430`) [CODE] ([R24](../risk/risk-register.md#r24)).
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
  the db sync runs while old engines are still active, and all engines restart together after it (2025.1, unchanged:
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
| Play | site.yml:722 |
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
- [RabbitMQ](rabbitmq.md) — the queue settings, always rendered into `heat.conf` in 2025.1
- [Component dependencies §6](dependencies.md#6-deployment-order-vs-runtime-dependency) — Heat, Horizon and Octavia come
  after Nova and Neutron in the deployment order
- [Components](index.md) — the other component pages
