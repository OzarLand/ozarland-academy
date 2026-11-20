---
title: RabbitMQ
description: "Where the 2024.1 study covers RabbitMQ: quorum queues by default, prechecks, the upgrade version check, tag impact, membership and upgrade risks."
tags: [rabbitmq, serial, upgrade, inventory, risk, dependencies, bugs, unknowns]
---

# RabbitMQ

This page is the starting point for RabbitMQ, the `rabbitmq` role: one container, `rabbitmq` (the container is named
after `project_name`, `roles/rabbitmq/defaults/main.yml:4`, which the role sets to `rabbitmq`,
`roles/rabbitmq/vars/main.yml:2`), on the control nodes of the example inventory (`inventory/multinode:90-91`). The
role is not applied by a play of `site.yml` itself: `site.yml:468` imports `rabbitmq.yml`, whose three plays all carry
the tag `rabbitmq`: apply the role (no `serial`), restart the hosts the handler put in the `rabbitmq_restart` group
(`serial: "33%"`), then post-configuration (`rabbitmq.yml:3-70`) [CODE]. Changed in 2024.1: outward RabbitMQ is
removed, with its three plays, its inventory group and its `enable_outward_rabbitmq` flag (no match for `outward` under
`ansible/`), and every play now sets `max_fail_percentage`, default 100 (`rabbitmq.yml:8-11,37-40,56-59`), which never
stops a play early ([Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)). New in 2024.1: quorum queues are on by
default ([F17](../reference/findings.md#f17)) and `upgrade` runs a version check that refuses to skip a RabbitMQ minor
version. The service card below summarises these plays. The lists below say where the study covers how to operate
it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the service card
follows them.

## Where to look

### Operate

- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Change control-plane membership
  §1.1](../operations/change-control-plane-membership.md#11-remove-or-replace-a-controller), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)
- **RabbitMQ version step:** `kolla-ansible rabbitmq-upgrade <version>` runs `rabbitmq-upgrade.yml` with
  `-e rabbitmq_version_suffix=<version>` (`tools/kolla-ansible:585-590`); that playbook imports `rabbitmq.yml` with
  `kolla_action: upgrade` and the image `rabbitmq-<version with dots replaced by hyphens>`
  (`rabbitmq-upgrade.yml:18-21`) [CODE]. The kolla 2024.1 tree defines two RabbitMQ images: `rabbitmq`, pinned to
  RabbitMQ 3.13 and Erlang 26.2 (kolla `docker/rabbitmq/rabbitmq/rabbitmq_packages_rpm.rocky:1-4`,
  `apt_preferences_rabbitmq.ubuntu:1-7`), and `rabbitmq-4-1`, pinned to RabbitMQ 4.1 and Erlang 27 (kolla
  `docker/rabbitmq/rabbitmq-4-1/rabbitmq_packages_rpm.rocky:1-4`) [CODE].

### Impact and risk

- **What the tag executes (`rabbitmq`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `rabbitmq`
- **Risks:** [R3](../risk/risk-register.md#r3), [R10](../risk/risk-register.md#r10)
- **Quorum queues by default:** [F17](../reference/findings.md#f17). `om_enable_rabbitmq_quorum_queues` now defaults to
  `true` (`group_vars/all.yml:266-268`; 2023.1: `false`), so the `[oslo_messaging_rabbit]` section of 26 templates in
  24 roles renders `rabbit_quorum_queue = true` (grep of `roles/*/templates`; e.g.
  `roles/nova/templates/nova.conf.j2:156-165`, `roles/nova-cell/templates/nova.conf.j2:207-216`,
  `roles/neutron/templates/neutron.conf.j2:146-155`) [CODE]. A cloud that kept the 2023.1 default therefore gets a
  changed configuration file, and a handler restart, for those services on its first 2024.1 run that renders configs,
  computes included. Three related options are new and off by default: `om_enable_queue_manager: false`, and
  `om_enable_rabbitmq_transient_quorum_queue` and `om_enable_rabbitmq_stream_fanout`, which follow it
  (`group_vars/all.yml:269-279`) [CODE]. [NOT AVAILABLE] What oslo.messaging does with existing classic queues when the
  services restart with `rabbit_quorum_queue = true`.

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Transport URLs:** `rpc_transport_url` and `notify_transport_url` list every host of the `rabbitmq` group one by
  one (`group_vars/all.yml:245,248,255,258`); nova-cell builds its own URLs from the same group by default
  (`roles/nova-cell/defaults/main.yml:191,200,206-207`) [CODE]. Still holds in 2024.1: a change of the `rabbitmq`
  membership changes the `transport_url` of every service that uses them.

### Evidence

- **Fact sheet:** [fact sheet B
  §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `rabbitmq`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services). Still holds in 2024.1: the only
  handler, "Restart rabbitmq container", restarts nothing; it adds the host to the group `rabbitmq_restart`, except
  for `kolla_action` `config` (`roles/rabbitmq/handlers/main.yml:2-6`), and the restart play then drains the node
  (`community.rabbitmq.rabbitmq_upgrade` `drain`, only when a `rabbitmq` container exists), recreates or restarts it
  and waits with `rabbitmqctl wait --timeout 60` (`roles/rabbitmq/tasks/restart_services.yml:2-39`), in
  `serial: "33%"` batches (`rabbitmq.yml:30-49`) [CODE].

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 3 (batch size): `ANSIBLE_SERIAL` covers
  `reconfigure`/`upgrade` and `-e kolla_serial=N` covers `deploy`; mariadb and rabbitmq ignore it: the RabbitMQ plays
  set no `serial` except the restart play, which has its own `serial: "33%"` (`rabbitmq.yml:3-70`, `:36`) [CODE].
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  RabbitMQ: cluster status, no partitions. Repeat after each batch.
- **`kolla-ansible prechecks` is stricter in 2024.1** ([F17](../reference/findings.md#f17)) [CODE]:
  - "Validate rabbitmq variables" fails when `om_enable_rabbitmq_high_availability` and
    `om_enable_rabbitmq_quorum_queues` are **equal**, so also when both are off
    (`roles/prechecks/tasks/service_checks.yml:67-72`); 2023.1 failed only when both were on. A new check fails when
    stream fanout is on without transient quorum queues (`:74-81`).
  - When a `rabbitmq` container exists and quorum queues are on, the RabbitMQ precheck lists the queues once and
    asserts that every queue whose name contains neither `reply_` nor `_fanout` is a quorum queue; two more asserts
    cover transient quorum queues and stream fanout when those are on (`roles/rabbitmq/tasks/precheck.yml:131-189`).
    With the 2024.1 defaults it therefore fails while classic queues exist; its message calls the migration a manual
    procedure. The HA block still asserts the `ha-all` policy when `om_enable_rabbitmq_high_availability` is on
    (`:107-129`). A cloud that kept the 2023.1 default (HA off) has no such policy, since 2023.1 runs removed it, and
    the message of that assert calls the move to mirrored queues manual too (`:115-123`). Both blocks carry the tag
    `rabbitmq-ha-precheck` (`:129`, `:189`).
  - These checks run only for `kolla_action` `precheck`, set by `kolla-ansible prechecks`
    (`tools/kolla-ansible:444-447`; the prechecks play, `site.yml:77-86`; the role entry point includes
    `<kolla_action>.yml`, `roles/rabbitmq/tasks/main.yml:2-3`). `deploy`, `reconfigure` and `upgrade` do not run them.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `rabbitmq`:
  safe on its own "yes on a healthy cluster; membership changes are R3"; prerequisites: no partitions, all nodes
  running.
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R10](../risk/risk-register.md#r10), precautions for a RabbitMQ image change (`upgrade`): maintenance window; watch
  for agent and compute services reported down. Still holds in 2024.1: `upgrade` does not stop every broker; the
  role renders the config, enables all stable feature flags on the running brokers, then checks the containers
  (`roles/rabbitmq/tasks/upgrade.yml:1-12`, `feature-flags.yml:2-5`), and the restart play drains, recreates and waits
  for each node in `serial: "33%"` batches (`rabbitmq.yml:30-49`, `roles/rabbitmq/tasks/restart_services.yml:9-39`)
  [CODE].
- **New in 2024.1: the version check refuses a skipped RabbitMQ minor version** [CODE]. `upgrade.yml` now imports
  `version-check.yml` first (`roles/rabbitmq/tasks/upgrade.yml:2`), as `deploy.yml` already did, and therefore also
  `reconfigure` (`deploy.yml:2`, `reconfigure.yml:2`). When a `rabbitmq` container exists, once, on the first host of
  the group (`version-check.yml:75-78`), it reads the running version with `rabbitmqctl --version` and the new one
  from a one-shot `rabbitmq_version_check` container of the target image (`:12-36`), then asserts that both have the
  same major version and at most one minor version between them, or that the step is 3.13 to 4.0 or 4.1 (`:44-64`).
  Otherwise it fails with "Looks like you're trying to run a skip-release upgrade!" and names the
  `kolla-ansible rabbitmq-upgrade` step to run first (`:59-64`). The downgrade assert follows (`:66-73`). The whole
  file carries the tag `rabbitmq-version-check` (`:79`), so `--skip-tags rabbitmq-version-check` skips it.
- **Consequence for an upgrade from 2023.1** [CODE, from the image pins]: the 2023.1 `rabbitmq` image pinned RabbitMQ
  3.11 (2023.1 kolla `docker/rabbitmq/rabbitmq/apt_preferences_rabbitmq.ubuntu:2`), the 2024.1 one pins 3.13 (kolla
  `docker/rabbitmq/rabbitmq/apt_preferences_rabbitmq.ubuntu:2`). A cloud still on the 2023.1 default image is two
  minor versions behind, and the 2024.1 version check fails until it runs 3.12 or 3.13. The kolla 2024.1 tree has no
  `rabbitmq-3-12` image (only `rabbitmq` and `rabbitmq-4-1`, kolla `docker/rabbitmq/`), while 2023.1 had
  `rabbitmq-3-12` and `rabbitmq-3-13`. [NOT AVAILABLE] Which RabbitMQ version a given cloud runs, and which image a
  `rabbitmq-upgrade 3.12` run with 2024.1 code would find in the registry.
- **A 4.1 step is undone by the next plain run** [CODE]: after `kolla-ansible rabbitmq-upgrade 4.1`, a `deploy`,
  `reconfigure` or `upgrade` with the default `rabbitmq_image` (`roles/rabbitmq/defaults/main.yml:30`) targets the
  3.13 image again, and the downgrade assert fails (`roles/rabbitmq/tasks/version-check.yml:66-73`) unless
  `rabbitmq_image` is overridden.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), first row `rabbitmq`: outward RabbitMQ
  `pull` looked up `outward_rabbitmq_services`. No longer holds in 2024.1 [CODE]: outward RabbitMQ is removed, and
  `pull` looks up `rabbitmq_services` through `project_name` (`roles/rabbitmq/tasks/pull.yml:2-3`,
  `roles/service-images-pull/tasks/main.yml:14`, `roles/rabbitmq/vars/main.yml:2`). The 2023.1 oddity of the outward
  post-configuration play, which included the whole role, is gone with it: the only post-configuration play includes
  `post-deploy.yml` (`rabbitmq.yml:63-67`), which enables the feature flags (`post-deploy.yml:2`).
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), second row `rabbitmq`: the image
  writes `.erlang.cookie` only in the bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`), which
  runs only when the volume was just created (`roles/rabbitmq/tasks/bootstrap.yml:2-26`); a cookie change recreates the
  brokers (env compare, `roles/rabbitmq/defaults/main.yml:13-16`, `roles/rabbitmq/tasks/check-containers.yml:10`) but
  they keep the old cookie, while `kolla_toolbox` gets the new one. Status: still holds in 2024.1 [CODE];
  consequences [NOT AVAILABLE].
- New in 2024.1 [CODE]: the data volume is `rabbitmq_datadir_volume` (default `rabbitmq`, `group_vars/all.yml:913`;
  `roles/rabbitmq/defaults/main.yml:52`), but the bootstrap still creates, and gates on, the volume named after
  `project_name` (`roles/rabbitmq/tasks/bootstrap.yml:2-8,26`). With the default the two are the same volume.
  [NOT AVAILABLE] What happens to the cookie when `rabbitmq_datadir_volume` is changed on an existing cloud: the
  volume `rabbitmq` already exists, so the bootstrap does not run for the new data volume.
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "RabbitMQ": the sources do not establish whether nova-compute heartbeats are lost and services are reported down
  while brokers are drained and restarted on upgrade ([R10](../risk/risk-register.md#r10)); whether, during a
  one-by-one restart, nova-compute and the agents lose RPC, RPC-backed API calls time out and the agents reconnect by
  themselves; the consequences of a changed Erlang cookie; new in 2024.1, what oslo.messaging does with existing
  classic queues once `rabbit_quorum_queue = true` is rendered ([F17](../reference/findings.md#f17)).
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: RabbitMQ writes the Erlang cookie
  only in its bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`).
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [F17](../reference/findings.md#f17), "RabbitMQ quorum queues are on by default": the 2024.1 default changes every
  service's messaging config and fails `prechecks` while classic queues exist [CODE].
- [fact sheet B
  §2.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities". Checked against 2024.1 [CODE]: reconfigure with a config
  change is a drained restart in `serial: "33%"` batches (`roles/rabbitmq/tasks/reconfigure.yml:2`,
  `rabbitmq.yml:30-49`);
  `upgrade` is not a full outage of the message bus: `roles/rabbitmq/tasks/upgrade.yml:1-12` has no cluster-wide stop
  ([R10](../risk/risk-register.md#r10)); uncontrolled full stop (the brokers come back through the same batched
  restart play; which node starts first is [NOT AVAILABLE], `group_by` order); scaling the rabbitmq group changes
  `transport_url` (the templates of 25 roles reference `rpc_transport_url`, grep of `roles/*/templates`;
  `group_vars/all.yml:248,258`); password change; the `kolla-ansible pull` bug with outward RabbitMQ no longer applies
  (see above); `check.yml` is still empty (`roles/rabbitmq/tasks/check.yml:1`); the precheck still runs `getent` for
  every rabbit host on every rabbit host, N² lookups (`roles/rabbitmq/tasks/precheck.yml:61-77`), now only for the
  `rabbitmq` group. Changed in 2024.1: the `ha-all` policy removal no longer calls `docker exec` literally; it uses
  `kolla_container_engine` (`roles/rabbitmq/tasks/remove-ha-all-policy.yml:14,20`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 9 and 10: the RabbitMQ cookie is fixed at
  bootstrap [CODE; consequences NOT AVAILABLE]; `kolla_toolbox` gets the new cookie only when the `common` play runs
  (an untagged run or `-t common`; `roles/common/templates/rabbitmq-erlang.cookie.j2:1`,
  `roles/common/tasks/config.yml:272-282`, `site.yml:88-103`); recursive chown on data volumes at every start, the
  RabbitMQ mnesia directory among them [CODE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py rabbitmq -->

| Item | Value |
|---|---|
| Play | rabbitmq.yml (`import_playbook` at site.yml:468; 3 plays) |
| Tags | rabbitmq |
| Play host patterns | rabbitmq, rabbitmq_restart |
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
  `upgrade` both restart RabbitMQ in batches of 33 %, each node drained first; both run the version check first
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — RabbitMQ hosts
  are listed one by one in the configs of the services that use them
- [Common: fluentd, cron, kolla_toolbox](common.md) — `kolla_toolbox` gets the new cookie when
  `rabbitmq_cluster_cookie` changes and the `common` play runs
- [Technical findings F17](../reference/findings.md#f17) — quorum queues on by default and the stricter prechecks
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
