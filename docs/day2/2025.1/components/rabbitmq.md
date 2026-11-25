---
title: RabbitMQ
description: "The 2025.1 study of RabbitMQ: quorum and stream queues always on, RabbitMQ 4.0, prechecks, the version check, membership and upgrade risks."
tags: [rabbitmq, serial, upgrade, inventory, risk, dependencies, bugs, unknowns]
---

# RabbitMQ

This page is the starting point for RabbitMQ, the `rabbitmq` role: one container, `rabbitmq` (the container is named
after `project_name`, `roles/rabbitmq/defaults/main.yml:4`, which the role sets to `rabbitmq`,
`roles/rabbitmq/vars/main.yml:2`), on the control nodes of the example inventory (`inventory/multinode:90-91`). The
role is not applied by a play of `site.yml` itself: `site.yml:483` imports `rabbitmq.yml`, whose three plays all carry
the tag `rabbitmq`: apply the role (no `serial`), restart the hosts the handler put in the `rabbitmq_restart` group
(`serial: "33%"`), then post-configuration (`rabbitmq.yml:3-70`) [CODE]. Every play sets `max_fail_percentage`, default
100 (`rabbitmq.yml:8-11,37-40,56-59`), which never stops a play early
([Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)).

**Changed in 2025.1** [CODE]:
- **Queues:** `om_enable_rabbitmq_high_availability`, `om_enable_rabbitmq_quorum_queues` and
  `om_enable_rabbitmq_transient_quorum_queue` are gone; every service renders `use_queue_manager = true`,
  `rabbit_quorum_queue = true` and `rabbit_transient_quorum_queue = true`, and `rabbit_stream_fanout = true` while
  `om_enable_rabbitmq_stream_fanout` keeps its default `true` (`group_vars/all.yml:292`;
  `roles/nova/templates/nova.conf.j2:142-156`) ([F17](../reference/findings.md#f17)).
- **Version:** the default image moves from RabbitMQ 3.13 to **4.0** (kolla
  `docker/rabbitmq/rabbitmq/apt_preferences_rabbitmq.ubuntu:1-3`), and there is no `kolla-ansible rabbitmq-upgrade`
  command any more.
- **Restarts:** no config task notifies; the shared `service-check-containers` role compares the container and
  notifies `Restart rabbitmq container` (`roles/rabbitmq/tasks/check-containers.yml:2-3`); the image name takes
  `docker_image_name_prefix` (`roles/rabbitmq/defaults/main.yml:30`); `check.yml` runs the `service-check` role of
  `kolla-ansible check` (`roles/rabbitmq/tasks/check.yml:2-4`).

The service card below summarises these plays. The lists below say where the study covers how to operate it, its
impact, its dependencies and the evidence, what to check around a run and what stays open; the service card follows
them.

## Where to look

### Operate

- **Scenario:** [Change control-plane membership
  §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)
- **Command:** [Change control-plane membership
  §1.1](../operations/change-control-plane-membership.md#11-remove-or-replace-a-controller), [Command quick lookup by
  tag](../operations/command-quick-lookup.md)
- **RabbitMQ version step, changed in 2025.1** [CODE]: the CLI has no `rabbitmq-upgrade` command
  (`setup.cfg:50-77`). The playbook `rabbitmq-upgrade.yml` is still in the tree: it imports `rabbitmq.yml` with
  `kolla_action: upgrade` and the image `rabbitmq-<rabbitmq_version_suffix with dots replaced by hyphens>`, a name that
  ignores `docker_image_name_prefix` (`rabbitmq-upgrade.yml:18-21`). The kolla 2025.1 tree defines two RabbitMQ images:
  `rabbitmq`, pinned to RabbitMQ 4.0 and Erlang 26.2 (kolla `docker/rabbitmq/rabbitmq/rabbitmq_packages_rpm.rocky:1-4`,
  `apt_preferences_rabbitmq.ubuntu:1-3`), and `rabbitmq-4-1`, pinned to RabbitMQ 4.1 and Erlang 27 (kolla
  `docker/rabbitmq/rabbitmq-4-1/rabbitmq_packages_rpm.rocky:1-4`). To move to 4.1, an operator can set
  `rabbitmq_image` to the `rabbitmq-4-1` image and run `upgrade -t rabbitmq` (the default is set at
  `roles/rabbitmq/defaults/main.yml:30`). [NOT AVAILABLE] Whether the cliff CLI can run `rabbitmq-upgrade.yml` some
  other way; the commands of `kolla_ansible/cli/commands.py` each name their playbook.
- **Reset the state:** `kolla-ansible rabbitmq-reset-state` runs `stop_app`, `force_reset`, `start_app` and
  `await_online_nodes` on every rabbitmq host at once (`kolla_ansible/cli/commands.py:426-434`;
  `roles/rabbitmq/tasks/reset-state.yml:1-16`) [CODE].

### Impact and risk

- **What the tag executes (`rabbitmq`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `rabbitmq`
- **Risks:** [R3](../risk/risk-register.md#r3), [R10](../risk/risk-register.md#r10)
- **Quorum, transient quorum and stream fanout always on:** [F17](../reference/findings.md#f17). The
  `[oslo_messaging_rabbit]` section of 26 templates in 24 roles renders `rabbit_quorum_queue = true` (grep of
  `roles/*/templates`; e.g. `roles/nova/templates/nova.conf.j2:151-156`, `roles/nova-cell/templates/nova.conf.j2:201-206`,
  `roles/neutron/templates/neutron.conf.j2:139-144`) [CODE]. A 2024.1 cloud with the 2024.1 defaults already had
  quorum queues, but not the queue manager, transient quorum queues or stream fanout (2024.1
  `group_vars/all.yml:269-279`). Its first 2025.1 run that renders configs therefore changes the messaging config of
  those services, computes included, and restarts them. [NOT AVAILABLE] What oslo.messaging does with the existing
  classic `reply_` queues and fanout exchanges when the services restart with these options; to be confirmed by the
  community.

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components)
- **Transport URLs:** `rpc_transport_url` and `notify_transport_url` list every host of the `rabbitmq` group one by
  one (`group_vars/all.yml:274,284`); nova-cell builds its own URLs from the same group by default
  (`roles/nova-cell/defaults/main.yml:202,217-218`) [CODE]. Still holds in 2025.1: a change of the `rabbitmq`
  membership changes the `transport_url` of every service that uses them.

### Evidence

- **Fact sheet:** [fact sheet B
  §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `rabbitmq`), [Kolla
  images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services). The only handler, "Restart rabbitmq
  container", restarts nothing; it adds the host to the group `rabbitmq_restart` (`roles/rabbitmq/handlers/main.yml:2-4`),
  and the restart play then, when a `rabbitmq` container is listed, drains the node with
  `community.rabbitmq.rabbitmq_upgrade` `drain` if the group has more than one host, or runs `rabbitmqctl stop_app` on a
  single-node broker (new in 2025.1), recreates or restarts it and waits with `rabbitmqctl wait --timeout 60`
  (`roles/rabbitmq/tasks/restart_services.yml:2-49`), in `serial: "33%"` batches (`rabbitmq.yml:30-49`) [CODE].

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 3 (batch size): **changed in 2025.1**,
  `reconfigure` and `upgrade` always pass `kolla_serial=0` ([F19](../reference/findings.md#f19)) and only `deploy -e
  kolla_serial=N` batches; mariadb and rabbitmq ignore it anyway: the RabbitMQ plays set no `serial` except the restart
  play, which has its own `serial: "33%"` (`rabbitmq.yml:3-70`, `:36`) [CODE].
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  RabbitMQ: cluster status, no partitions. Repeat after each batch. **New in 2025.1:** `kolla-ansible check -t rabbitmq`
  fails when the `rabbitmq` container is missing, stopped or `unhealthy` (`roles/rabbitmq/tasks/check.yml:2-4`,
  `roles/service-check/tasks/main.yml:3-40`); it does not look at the cluster itself.
- **`kolla-ansible prechecks`, changed in 2025.1** ([F17](../reference/findings.md#f17)) [CODE]:
  - The `prechecks` role no longer compares HA and quorum settings; the variables are gone.
  - When a `rabbitmq` container exists, the RabbitMQ precheck lists the queues once and asserts, with no switch, that
    every queue whose name contains neither `reply_` nor `_fanout` is a quorum queue, that `reply_` queues are quorum
    queues, and that `_fanout` queues are streams while stream fanout is on
    (`roles/rabbitmq/tasks/precheck.yml:110-164`). A 2024.1 cloud with the 2024.1 defaults has classic `reply_` and
    fanout queues, so the precheck fails there until they are migrated; the message calls the migration manual and
    says it may take several hours (`:121-125`). The `ha-all` assert is gone. The block carries the tag
    `rabbitmq-ha-precheck` (`:164`).
  - These checks run only for `kolla_action` `precheck`, set by `kolla-ansible prechecks`
    (`kolla_ansible/cli/commands.py:99-110`; the prechecks play, `site.yml:77-86`; the role entry point includes
    `<kolla_action>.yml`, `roles/rabbitmq/tasks/main.yml:2-3`). `deploy`, `reconfigure` and `upgrade` do not run them.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `rabbitmq`:
  safe on its own "yes on a healthy cluster; membership changes are R3"; prerequisites: no partitions, all nodes
  running.
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R10](../risk/risk-register.md#r10), precautions for a RabbitMQ image change (`upgrade`): maintenance window; watch
  for agent and compute services reported down. Still holds in 2025.1: `upgrade` does not stop every broker; the role
  renders the config, enables all stable feature flags on the running brokers, then checks the containers
  (`roles/rabbitmq/tasks/upgrade.yml:1-10`, `feature-flags.yml:2-5`), and the restart play drains, recreates and waits
  for each node in `serial: "33%"` batches (`rabbitmq.yml:30-49`, `roles/rabbitmq/tasks/restart_services.yml:10-49`)
  [CODE].
- **The version check** [CODE]: `deploy.yml` and `upgrade.yml` import `version-check.yml` first
  (`roles/rabbitmq/tasks/deploy.yml:2`, `upgrade.yml:2`), and so does `reconfigure` (`reconfigure.yml:2`). When a
  `rabbitmq` container exists, once, on the first host of the group (`version-check.yml:76-80`), it reads the running
  version with `rabbitmqctl --version` and the new one from a one-shot `rabbitmq_version_check` container of the
  target image (`:13-38`), then asserts that both have the same major version and at most one minor version between
  them, or that the step is 3.13 to 4.0 or 4.1 (`:45-65`). Otherwise it fails with "Looks like you're trying to run a
  skip-release upgrade!" and, **an oddity in 2025.1**, names a `kolla-ansible rabbitmq-upgrade` step that the CLI no
  longer has (`:64`). The downgrade assert follows (`:67-74`). The whole file carries the tag `rabbitmq-version-check`
  (`:80`), so `--skip-tags rabbitmq-version-check` skips it.
- **Consequence for an upgrade from 2024.1** [CODE, from the image pins]: the 2024.1 `rabbitmq` image pinned RabbitMQ
  3.13, the 2025.1 one pins 4.0 (kolla `docker/rabbitmq/rabbitmq/apt_preferences_rabbitmq.ubuntu:2`), a step the check
  allows. A cloud that moved to the 2024.1 `rabbitmq-4-1` image is on 4.1, and the default 2025.1 image would be a
  downgrade that the check refuses (`version-check.yml:67-74`) unless `rabbitmq_image` points at the `rabbitmq-4-1`
  image again. [NOT AVAILABLE] Which RabbitMQ version a given cloud runs, and what RabbitMQ 4.0 does with a cluster
  that still has classic mirrored queues.

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `rabbitmq`: the image writes
  `.erlang.cookie` only in the bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`), which runs
  only when the volume was just created (`roles/rabbitmq/tasks/bootstrap.yml:2-26`); a cookie change recreates the
  brokers (env compare, `roles/rabbitmq/defaults/main.yml:13-16`, `roles/service-check-containers/tasks/main.yml:19`)
  but they keep the old cookie, while `kolla_toolbox` gets the new one. Status: still holds in 2025.1 [CODE];
  consequences [NOT AVAILABLE].
- The data volume is `rabbitmq_datadir_volume` (default `rabbitmq`, `group_vars/all.yml:1049`;
  `roles/rabbitmq/defaults/main.yml:52`), but the bootstrap still creates, and gates on, the volume named after
  `project_name` (`roles/rabbitmq/tasks/bootstrap.yml:2-8,26`). With the default the two are the same volume
  [CODE]. [NOT AVAILABLE] What happens to the cookie when `rabbitmq_datadir_volume` is changed on an existing cloud.
- **New in 2025.1, `ha-all` removal on every run** [CODE]: `remove-ha-all-policy.yml` now runs on every deploy,
  reconfigure and upgrade, with no condition, and clears an `ha-all` policy found on the first rabbitmq host
  (`roles/rabbitmq/tasks/deploy.yml:4`, `remove-ha-all-policy.yml:12-24`).
- **The HA tuning variables are dead** [CODE]: `rabbitmq_ha_replica_count`, `rabbitmq_ha_promote_on_shutdown`,
  `rabbitmq_message_ttl_ms` and `rabbitmq_queue_expiry_ms` are still defined (`roles/rabbitmq/defaults/main.yml:65-85`),
  but `definitions.json.j2` renders `"policies":[]` unconditionally (`roles/rabbitmq/templates/definitions.json.j2:13`).
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "RabbitMQ": the sources do not establish whether nova-compute heartbeats are lost and services are reported down
  while brokers are drained and restarted on upgrade ([R10](../risk/risk-register.md#r10)); whether, during a
  one-by-one restart, nova-compute and the agents lose RPC and reconnect by themselves; the consequences of a changed
  Erlang cookie; what oslo.messaging does with existing classic transient queues once transient quorum queues and
  stream fanout are rendered ([F17](../reference/findings.md#f17)). These points are to be confirmed by the community.
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: RabbitMQ writes the Erlang cookie
  only in its bootstrap container (kolla `docker/rabbitmq/rabbitmq/extend_start.sh:7-18`).
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [F17](../reference/findings.md#f17), "RabbitMQ quorum queues are on by default": the only choice in 2025.1 [CODE].
- [fact sheet B
  §2.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities". Checked against 2025.1 [CODE]: reconfigure with a config
  change is a drained restart in `serial: "33%"` batches (`roles/rabbitmq/tasks/reconfigure.yml:2`,
  `rabbitmq.yml:30-49`); `upgrade` is not a full outage of the message bus: `roles/rabbitmq/tasks/upgrade.yml:1-10` has
  no cluster-wide stop ([R10](../risk/risk-register.md#r10)); uncontrolled full stop (the brokers come back through the
  same batched restart play; which node starts first is [NOT AVAILABLE], `group_by` order); scaling the rabbitmq group
  changes `transport_url` (the templates of 25 roles reference `rpc_transport_url`, grep of `roles/*/templates`;
  `group_vars/all.yml:274,284`); password change; the precheck still runs `getent` for every rabbit host on every
  rabbit host, N² lookups (`roles/rabbitmq/tasks/precheck.yml:62-78`).
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 9 and 10: the RabbitMQ cookie is fixed at
  bootstrap [CODE; consequences NOT AVAILABLE]; `kolla_toolbox` gets the new cookie only when the `common` play runs
  (an untagged run or `-t common`; `roles/common/templates/rabbitmq-erlang.cookie.j2:1`,
  `roles/common/tasks/config.yml:241-249`, `site.yml:88-103`); recursive chown on data volumes at every start, the
  RabbitMQ mnesia directory among them (`roles/rabbitmq/templates/rabbitmq.json.j2:59-70`) [CODE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py rabbitmq -->

| Item | Value |
|---|---|
| Play | rabbitmq.yml (`import_playbook` at site.yml:483; 3 plays) |
| Tags | rabbitmq |
| Play host patterns | rabbitmq, rabbitmq_restart |
| Node types in play (example inventory) | control |
| Node types running its containers | – |
| Containers | `rabbitmq` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | version-check → remove-ha-all-policy → config → check-containers → bootstrap |
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
- [Technical findings F17](../reference/findings.md#f17) — quorum queues, the only choice in 2025.1
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
