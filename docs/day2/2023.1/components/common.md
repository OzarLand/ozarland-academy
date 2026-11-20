---
title: "Common: fluentd, cron, kolla_toolbox"
description: "Where the study covers the common role (fluentd, cron, kolla_toolbox): its own play, the -t common tag, how its changes reach hosts, risks and open points."
tags: [fluentd, cron, kolla-toolbox, tags, loop-notify, kolla-set-configs, risk, dependencies, bugs, unknowns]
---

# Common: fluentd, cron, kolla_toolbox

This page is the starting point for the `common` role: the containers `fluentd`, `kolla_toolbox` and `cron`, on the
compute, control, monitoring, network and storage nodes of the example inventory. In 2023.1 the role is no meta
dependency of any other role (no `roles/*/meta` directory): it runs only in its own play, "Apply role common", on the
groups `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`, with the play tag `common` (`site.yml:86-97`). `-t common`
therefore runs it, and a service tag such as `-t nova` does not [CODE]. The lists below say where the study covers how
to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the
service card follows them.

## Where to look

### Operate

- **Scenario:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md)
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox):
  `kolla-ansible -i multinode -t common reconfigure`, optionally with `--limit`

### Impact and risk

- **What the tag executes (`common`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `common`; why
  the
  tag now reaches the included tasks: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)
- **Risks:** [R2](../risk/risk-register.md#r2); [R25](../risk/risk-register.md#r25) does not apply to 2023.1 (the
  risk register keeps the entry and says why)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components) (row "Fluentd"), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)

### Evidence

- **Fact sheet:** – (see [Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard), which also records that the
  `common_run` guard is gone)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `fluentd`, `cron`,
  `kolla-toolbox`)
- **Also:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md); handlers:
  [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 7 (scope): `-t common` runs the common
  role in its own play, and service tags no longer run it (`site.yml:86-97`, `roles/common/tasks/main.yml:2`).
- [R2](../risk/risk-register.md#r2), precautions: treat `enable_*` changes as fleet-wide changes for the `common` play;
  roll out with `--limit` batches or `ANSIBLE_SERIAL` (the play has `serial: kolla_serial`, `site.yml:93`).
- [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §4](../operations/apply-common-changes.md#4-sequence-risks-and-verification), verification: before, `genconfig`, then
  `kolla_set_configs --check` in each of `fluentd`, `cron` and `kolla_toolbox` (1 in any of them = all three will
  restart, by loop-notify); the check does not cover image or volume changes. After, `docker ps` shows fresh start
  times, `docker logs fluentd` has no parse errors and logs still reach the configured output.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `common`:
  config files that can change: `config.json`, `td-agent.conf`, the cron logrotate config and the kolla_toolbox files,
  on every host of `common` [CODE] (`roles/common/tasks/config.yml`); safe on its own: "yes; the way to push common
  config fleet-wide".

### Known limits and open points

- [F2](../reference/findings.md#f2), "`-t common` is a no-op": does not hold in 2023.1. The tag `common` is on the play
  (`site.yml:94-95`), and the tasks of the dynamic include in `roles/common/tasks/main.yml:2` inherit it through their
  parent block (ansible-core 2.14.18 `lib/ansible/plugins/strategy/__init__.py:819-820`,
  `lib/ansible/playbook/block.py:355-363`) [CODE] ([Apply `common` changes
  §2](../operations/apply-common-changes.md#2-the-tag-does-nothing)). The reverse surprise is new: a tagged service run
  no longer applies pending `common` changes, which wait for an untagged run or `-t common`.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": still holds. `Check common containers` loops over
  `common_services` with `notify: "Restart {{ item.key }} container"` (`roles/common/tasks/check-containers.yml:2-17`),
  and ansible-core 2.14.18 notifies every handler of a changed looped result
  (`lib/ansible/plugins/strategy/__init__.py:614-631`): a change for one container restarts all three on that host
  [CODE].
- [Q10](../troubleshooting/open-questions.md#q10) compares Ansible 2.8.20 and 2.9.27 and does not cover
  ansible-core 2.14.18; for 2023.1, F1 and F2 are settled by the code cited in the two items above.
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": for `common`, the
  `enable_*` flags of the OpenStack services (`fluentd_input_openstack_services`,
  `roles/common/defaults/main.yml:138-202`)
  and the logrotate services list end up in `td-agent.conf` and `logrotate.conf` on every common host [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#running-vms-and-compute-hosts): the sources do not
  establish whether restarts that touch none of the containers the study traces to running VMs (the `common` containers,
  the control-plane services) affect running VMs, APIs or traffic another way.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour),
  row "fluentd": the sources do not establish whether the tail read positions (in `/var/run/td-agent/`, on no volume,
  `roles/common/templates/conf/input/00-global.conf.j2:12`) survive a config-only restart, and whether they are lost on
  a recreate.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 9: a changed `rabbitmq_cluster_cookie`
  recreates the brokers but their cookie file keeps the old value, while `kolla_toolbox` gets the new one
  [CODE; consequences NOT AVAILABLE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py common -->

| Item | Value |
|---|---|
| Play | site.yml:86 |
| Tags | common |
| Play host patterns | cron, fluentd, kolla-logs, kolla-toolbox |
| Node types in play (example inventory) | compute, control, monitoring, network, storage |
| Node types running its containers | compute, control, monitoring, network, storage |
| Containers | `fluentd`, `kolla_toolbox`, `cron` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `admin-openrc.sh.j2`, `clouds.yaml.j2`, `conf/filter/00-record_transformer.conf.j2`, `conf/filter/01-rewrite.conf.j2`, `conf/filter/02-parser.conf.j2`, `conf/format/apache_access.conf.j2`, `conf/format/wsgi_access.conf.j2`, `conf/input/00-global.conf.j2`, `conf/input/01-syslog.conf.j2`, `conf/input/02-mariadb.conf.j2`, `conf/input/03-rabbitmq.conf.j2`, `conf/input/04-openstack-wsgi.conf.j2`, `conf/input/05-libvirt.conf.j2`, `conf/input/08-prometheus.conf.j2`, `conf/input/10-openvswitch.conf.j2`, `conf/output/00-local.conf.j2`, `conf/output/01-es.conf.j2`, `conf/output/03-opensearch.conf.j2`, `cron-logrotate-ansible.conf.j2`, `cron-logrotate-aodh.conf.j2`, `cron-logrotate-barbican.conf.j2`, `cron-logrotate-blazar.conf.j2`, `cron-logrotate-ceilometer.conf.j2`, `cron-logrotate-cinder.conf.j2`, `cron-logrotate-cloudkitty.conf.j2` … (+56) |
| Handlers (definition order) | Restart fluentd container; Restart kolla-toolbox container; Initializing toolbox container using normal user; Restart cron container |
| Key variables | `enable_fluentd`, `enable_* (all, via td-agent/logrotate)`, `elasticsearch_address`, `enable_monasca` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md) — the commands that
  push `common` changes, what restarts and how to verify
- [Chrony](chrony.md) — `-t chrony`, the Ussuri way to push `common` changes; no chrony role or play in 2023.1
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — the tag semantics that make
  `-t common` work in 2023.1
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common_run` guard (gone in 2023.1) and the global `fluentd` and `cron` configs
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host
- [Components](index.md) — the other component pages
