---
title: RabbitMQ
description: "Where the study covers RabbitMQ (six plays in rabbitmq.yml): tag impact, membership and upgrade risks, dependencies, known bugs and open points."
tags: [rabbitmq, serial, upgrade, inventory, risk, dependencies, bugs, unknowns]
---

# RabbitMQ

This page is the starting point for RabbitMQ, the `rabbitmq` role: the containers `rabbitmq` and `outward_rabbitmq`
(the container is named after `project_name`, `roles/rabbitmq/defaults/main.yml:4`; `project_name: outward_rabbitmq`
for the outward instance, `rabbitmq.yml:71`), on the control nodes of the example inventory
(`inventory/multinode:92-96`). The role is not applied by a play of `site.yml` itself: `site.yml:438` imports
`rabbitmq.yml`, whose six plays all carry the tag `rabbitmq`: for `rabbitmq` and then for `outward-rabbitmq`
(when `enable_outward_rabbitmq`), apply the role (no `serial`), restart the hosts the handler put in the
`<project>_restart` group (`serial: "33%"`), then post-configuration (`rabbitmq.yml:3-115`) [CODE]. The service
card below summarises these plays. The lists below say where the study covers how to operate it, its impact, its
dependencies and the evidence, what to check around a run and what stays open; the service card follows them.

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
  for agent and compute services reported down. In 2023.1 `upgrade` no longer stops every broker: the restart play
  drains each node (`rabbitmq_upgrade` `drain`), recreates it and waits with `rabbitmqctl wait --timeout 60`, in
  `serial: "33%"` batches (`rabbitmq.yml:26-41`, `roles/rabbitmq/tasks/restart_services.yml:9-39`) [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), first row `rabbitmq`: outward RabbitMQ
  `pull` looks up `outward_rabbitmq_services`. Status in 2023.1: [CODE]: with outward RabbitMQ enabled, the outward
  plays set `project_name: outward_rabbitmq` (`rabbitmq.yml:71`) and no `kolla_role_name`, so
  `service-images-pull` looks up `outward_rabbitmq_services` (`roles/rabbitmq/tasks/pull.yml:2-3`,
  `roles/service-images-pull/tasks/main.yml:14`); that variable is not defined anywhere, the `vars` lookup raises an
  undefined-variable error (ansible-core 2.14.18 `lib/ansible/plugins/lookup/vars.py:94-104`) and "Pull images" fails
  on the outward-rabbitmq hosts.
- New in 2023.1 [CODE]: the outward post-configuration play includes the whole role, not `post-deploy.yml`
  (`rabbitmq.yml:100-115`, no `tasks_from`, unlike `:51-55` for `rabbitmq`). On `deploy` and `reconfigure` it
  therefore runs the deploy flow of the role again on the outward-rabbitmq hosts (`roles/rabbitmq/tasks/main.yml:2-3`)
  instead of `feature-flags.yml` (`post-deploy.yml:2`). [NOT AVAILABLE] Whether the outward brokers then run without
  their feature flags enabled, and with what consequence.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `rabbitmq`: the image
  writes `.erlang.cookie` only in the bootstrap container (new volume); a cookie change recreates the brokers (env
  compare) but they keep the old cookie, while `kolla_toolbox` gets the new one. Status: [CODE]; consequences
  [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "RabbitMQ": the sources do not establish whether nova-compute heartbeats are lost and services are reported down
  while brokers are drained and restarted on upgrade ([R10](../risk/risk-register.md#r10)); whether, during a
  one-by-one restart, nova-compute and the agents lose RPC, RPC-backed API calls time out and the agents reconnect by
  themselves; the consequences of a changed Erlang cookie.
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: RabbitMQ writes the Erlang cookie
  only in its bootstrap container.
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [fact sheet B
  §2.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities", eight items. Checked against 2023.1 [CODE]: reconfigure with a
  config change (now a drained restart in `serial: "33%"` batches, see R10 above); "upgrade = full outage of the
  message bus" no longer holds: `roles/rabbitmq/tasks/upgrade.yml:2-10` has no cluster-wide stop
  ([R10](../risk/risk-register.md#r10));
  uncontrolled full stop (the brokers come back through the same batched restart play; which node starts first is
  [NOT AVAILABLE], `group_by` order); scaling the rabbitmq group changes `transport_url` (the templates of 30 roles
  reference `rpc_transport_url`, grep of `roles/*/templates`; `group_vars/all.yml:212,222`); password change; the
  `kolla-ansible pull` bug with outward rabbitmq enabled (still present, see above); `check.yml` is empty
  (`roles/rabbitmq/tasks/check.yml`), while `rabbitmq_hostname` no longer exists in 2023.1 (no match in `ansible/`);
  the precheck still runs `getent` for every rabbit host on every rabbit host, N² lookups
  (`roles/rabbitmq/tasks/precheck.yml:65-69,155-159`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 9 and 10: the RabbitMQ cookie is fixed at
  bootstrap [CODE; consequences NOT AVAILABLE]; `kolla_toolbox` gets the new cookie only when the `common` play runs
  (an untagged run or `-t common`; `roles/common/templates/rabbitmq-erlang.cookie.j2:1`, `site.yml:86-97`); recursive
  chown on data volumes at every start, the RabbitMQ mnesia
  directory among them [CODE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py rabbitmq -->

| Item | Value |
|---|---|
| Play | rabbitmq.yml (`import_playbook` at site.yml:438; 6 plays) |
| Tags | rabbitmq |
| Play host patterns | rabbitmq, rabbitmq_restart, outward-rabbitmq, outward_rabbitmq_restart |
| Node types in play (example inventory) | control |
| Node types running its containers | – |
| Containers | `rabbitmq` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | version-check → remove-ha-all-policy (if) → config → check-containers → bootstrap |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, feature-flags.yml, loadbalancer.yml, main.yml, post-deploy.yml, precheck.yml, pull.yml, reconfigure.yml, remove-ha-all-policy.yml, reset-state.yml, restart_services.yml, stop.yml, upgrade.yml, version-check.yml |
| Templates | `advanced.config.j2`, `definitions.json.j2`, `enabled_plugins.j2`, `erl_inetrc.j2`, `rabbitmq-env.conf.j2`, `rabbitmq.conf.j2`, `rabbitmq.json.j2` |
| Handlers (definition order) | Restart rabbitmq container |
| Key variables | `enable_rabbitmq`, `om_rpc_*`, `rabbitmq_*`, `rpc_transport_url` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Change control-plane membership](../operations/change-control-plane-membership.md) — changing the `rabbitmq`
  membership changes the transport URL everywhere
- [Update container images §4](../operations/update-container-images.md#4-risks) — with a tag change, `deploy` and
  `upgrade` both restart RabbitMQ in batches of 33 %, each node drained first
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — RabbitMQ hosts
  are listed one by one in the configs of the services that use them
- [Common: fluentd, cron, kolla_toolbox](common.md) — `kolla_toolbox` gets the new cookie when
  `rabbitmq_cluster_cookie` changes and the `common` play runs
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
