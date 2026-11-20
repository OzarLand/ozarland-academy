---
title: RabbitMQ
description: Where the study covers RabbitMQ (role rabbitmq, two plays), from tag impact and the membership and upgrade risks to dependencies, known bugs and open points.
tags: [rabbitmq, serial, upgrade, inventory, risk, dependencies, bugs, unknowns]
---

# RabbitMQ

This page is the starting point for RabbitMQ, the `rabbitmq` role: the containers `rabbitmq` and `outward_rabbitmq`, on
the control nodes of the example inventory. Two plays apply the role, `rabbitmq` and `outward-rabbitmq`, and they share
the tag `rabbitmq`. The lists below say where the study covers how to operate it, its impact, its dependencies and the
evidence, what to check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Change control-plane membership
  §1.1](../operations/change-control-plane-membership.md#11-remove-or-replace-a-controller), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)

### Impact and risk

- **What the tag executes (`rabbitmq`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `rabbitmq`
- **Risks:** [R3](../risk/risk-register.md#r3), [R10](../risk/risk-register.md#r10)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)

### Evidence

- **Fact sheet:** [fact sheet B
  §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `rabbitmq`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 3 (batch size): `ANSIBLE_SERIAL` covers
  `reconfigure`/`upgrade` and `-e kolla_serial=N` covers `deploy`; mariadb and rabbitmq ignore it.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  RabbitMQ: cluster status, no partitions. Repeat after each batch.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `rabbitmq`:
  safe on its own "yes on a healthy cluster; membership changes are R3"; prerequisites: no partitions, all nodes
  running.
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R10](../risk/risk-register.md#r10), precautions for a RabbitMQ image change (`upgrade`): maintenance window; watch
  for agent and compute services reported down.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), first row `rabbitmq`: outward RabbitMQ
  `pull` looks up `outward_rabbitmq_services`. Status: [CODE]: with outward RabbitMQ enabled, that variable is not
  defined anywhere, the `vars` lookup raises an undefined-variable error and "Pull images" fails on the
  outward-rabbitmq hosts.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `rabbitmq`: the image
  writes `.erlang.cookie` only in the bootstrap container (new volume); a cookie change recreates the brokers (env
  compare) but they keep the old cookie, while `kolla_toolbox` gets the new one. Status: [CODE]; consequences
  [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "RabbitMQ": the sources do not establish whether nova-compute heartbeats are lost and services are reported down
  during the upgrade outage ([R10](../risk/risk-register.md#r10)); whether, during a one-by-one restart, nova-compute
  and the agents lose RPC, RPC-backed API calls time out and the agents reconnect by themselves; the consequences of a
  changed Erlang cookie.
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: RabbitMQ writes the Erlang cookie
  only in its bootstrap container.
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [fact sheet B
  §2.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities", eight items: reconfigure with a config change; upgrade = full
  outage of the message bus; uncontrolled full stop; scaling the rabbitmq group changes `transport_url` in about 36
  services; password change; the `kolla-ansible pull` bug with outward rabbitmq enabled; `check.yml` is empty, and
  `rabbitmq_hostname` is dead code; the precheck does N² lookups.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 9 and 10: the RabbitMQ cookie is fixed at
  bootstrap [CODE; consequences NOT AVAILABLE]; recursive chown on data volumes at every start, the RabbitMQ mnesia
  directory among them [CODE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py rabbitmq -->

| Item | Value |
|---|---|
| Play | site.yml:535, site.yml:555 |
| Tags | rabbitmq |
| Play host patterns | rabbitmq, outward-rabbitmq |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `rabbitmq`, `outward_rabbitmq` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, restart_services.yml, stop.yml, upgrade.yml |
| Templates | `advanced.config.j2`, `definitions.json.j2`, `erl_inetrc.j2`, `rabbitmq-env.conf.j2`, `rabbitmq.conf.j2`, `rabbitmq.json.j2` |
| Handlers (definition order) | Restart first rabbitmq container; Restart remaining rabbitmq containers |
| Key variables | `enable_rabbitmq`, `om_rpc_*`, `rabbitmq_*`, `rpc_transport_url` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Change control-plane membership](../operations/change-control-plane-membership.md) — changing the `rabbitmq`
  membership changes the transport URL everywhere
- [Update container images §4](../operations/update-container-images.md#4-risks) — with a tag change applied by
  `deploy`, RabbitMQ is restarted node by node, not stopped cluster-wide
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — RabbitMQ hosts
  are listed one by one in the configs of the services that use them
- [Common: fluentd, cron, kolla_toolbox](common.md) — `kolla_toolbox` gets the new cookie when
  `rabbitmq_cluster_cookie` changes
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
