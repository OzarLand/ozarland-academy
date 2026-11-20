---
title: "Common: fluentd, cron, kolla_toolbox"
description: Where the study covers the common role (fluentd, cron, kolla_toolbox), from why -t common is a no-op and how its changes reach hosts to risks and open points.
tags: [fluentd, cron, kolla-toolbox, tags, loop-notify, kolla-set-configs, risk, dependencies, bugs, unknowns]
---

# Common: fluentd, cron, kolla_toolbox

This page is the starting point for the `common` role: the containers `fluentd`, `kolla_toolbox` and `cron`, on the
compute, control, monitoring, network and storage nodes of the example inventory. The role is a meta dependency of 68
roles (not `memcached`, `multipathd` or the helper roles): it runs in the first play that reaches each host and inherits
the tag of that play, and `-t common` alone is a no-op. The lists below say where the study covers how to operate it,
its impact, its dependencies and the evidence, what to check around a run and what stays open; the service card follows
them.

## Where to look

### Operate

- **Scenario:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md)
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)

### Impact and risk

- **What the tag executes (`common`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `common`; why it
  is a no-op: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)
- **Risks:** [R25](../risk/risk-register.md#r25), [R2](../risk/risk-register.md#r2)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components) (row "Fluentd"), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)

### Evidence

- **Fact sheet:** – (see [Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard))
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `fluentd`, `cron`,
  `kolla-toolbox`)
- **Also:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md); handlers:
  [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 7 (scope): never use `-t common` expecting
  it to do something.
- [R25](../risk/risk-register.md#r25), precautions: use `-t chrony` (all hosts) or a service tag; verify with
  `docker exec … kolla_set_configs --check`.
- [R2](../risk/risk-register.md#r2), precautions: treat `enable_*` changes as fleet-wide changes; roll out with
  `--limit` batches.
- [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §4](../operations/apply-common-changes.md#4-sequence-risks-and-verification), verification: before, `genconfig`, then
  `kolla_set_configs --check` in each of `fluentd`, `cron` and `kolla_toolbox` (1 in any of them = all three will
  restart, by loop-notify); the check does not cover image or volume changes. After, `docker ps` shows fresh start
  times, `docker logs fluentd` has no parse errors and logs still reach the configured output.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `common`:
  config files that can change: none (no-op) [CODE]; safe on its own: "safe but does nothing".

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `common`: `-t common` no-op
  ([F2](../reference/findings.md#f2)). Status: [CODE].
- [F2](../reference/findings.md#f2), "`-t common` is a no-op": tags on the dynamic `include_tasks` do not propagate to
  the included tasks [CODE]. Why it matters: `common` changes (fluentd/cron/toolbox) are applied by whatever run first
  reaches the host, often unexpectedly.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": a change for one container restarts every container of
  that role on that host [CODE].
- [Q10](../troubleshooting/open-questions.md#q10), answered from the source [CODE]: the code that produces
  [F1](../reference/findings.md#f1) and [F2](../reference/findings.md#f2) is the same in Ansible 2.8.20 and 2.9.27.
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#running-vms-and-compute-hosts): the sources do not
  establish whether restarts that touch none of the containers the study traces to running VMs (the `common` containers,
  the control-plane services) affect running VMs, APIs or traffic another way.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour),
  row "fluentd": the sources do not establish whether the tail read positions survive a config-only restart, and whether
  they are lost on a recreate.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 9: a changed `rabbitmq_cluster_cookie`
  recreates the brokers but their cookie file keeps the old value, while `kolla_toolbox` gets the new one
  [CODE; consequences NOT AVAILABLE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py common -->

| Item | Value |
|---|---|
| Play | meta dependency of 68 roles (not `memcached`, `multipathd` or the helper roles); runs in the first play that reaches each host |
| Tags | inherits the tag of the first play reaching the host (`-t common` alone is a no-op) |
| Play host patterns | first play reaching each host (chrony by default) |
| Node types in play (example inventory) | compute, control, monitoring, network, storage |
| Node types running its containers | compute, control, monitoring, network, storage |
| Containers | `fluentd`, `kolla_toolbox`, `cron` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `admin-openrc.sh.j2`, `conf/filter/00-record_transformer.conf.j2`, `conf/filter/01-rewrite-0.12.conf.j2`, `conf/filter/01-rewrite-0.14.conf.j2`, `conf/filter/02-parser.conf.j2`, `conf/format/apache_access.conf.j2`, `conf/format/wsgi_access.conf.j2`, `conf/format/wsgi_python.conf.j2`, `conf/input/00-global.conf.j2`, `conf/input/01-syslog.conf.j2`, `conf/input/02-mariadb.conf.j2`, `conf/input/03-rabbitmq.conf.j2`, `conf/input/04-openstack-wsgi.conf.j2`, `conf/input/05-libvirt.conf.j2`, `conf/input/06-zookeeper.conf.j2`, `conf/input/07-kafka.conf.j2`, `conf/input/09-monasca.conf.j2`, `conf/output/00-local.conf.j2`, `conf/output/01-es.conf.j2`, `conf/output/02-monasca.conf.j2`, `cron-logrotate-ansible.conf.j2`, `cron-logrotate-aodh.conf.j2`, `cron-logrotate-barbican.conf.j2`, `cron-logrotate-blazar.conf.j2`, `cron-logrotate-ceilometer.conf.j2` … (+63) |
| Handlers (definition order) | Restart fluentd container; Restart kolla-toolbox container; Initializing toolbox container using normal user; Restart cron container |
| Key variables | `enable_fluentd`, `enable_* (all, via td-agent/logrotate)`, `elasticsearch_address`, `enable_monasca` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md) — the commands that
  push `common` changes, what restarts and how to verify
- [Chrony](chrony.md) — `-t chrony` reaches every host (chrony runs everywhere by default) and is the recommended way to
  push `common` changes
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — the tag semantics that make
  `-t common` a no-op
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common_run` guard and the global `fluentd` and `cron` configs
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host
- [Components](index.md) — the other component pages
