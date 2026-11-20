---
title: "Common: fluentd, cron, kolla_toolbox"
description: "Where the 2024.1 study covers the common role (fluentd, cron, kolla_toolbox): its own play, the -t common tag, how changes reach hosts, risks."
tags: [fluentd, cron, kolla-toolbox, tags, loop-notify, kolla-set-configs, risk, dependencies, bugs, unknowns]
---

# Common: fluentd, cron, kolla_toolbox

This page is the starting point for the `common` role: the containers `fluentd`, `kolla_toolbox` and `cron`, on the
compute, control, monitoring, network and storage nodes of the example inventory. In 2024.1 the role is still no meta
dependency of any other role (no `roles/*/meta` directory): it runs only in its own play, "Apply role common", on the
groups `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`, with the play tag `common` (`site.yml:88-103`). `-t common`
therefore runs it, and a service tag such as `-t nova` does not [CODE]. New in 2024.1, its config step also makes sure
the fluentd image is on the host and reads two labels from it (`roles/common/tasks/config.yml:42-91`), so even a
config-only run of the role can pull that image [CODE]. The lists below say where the study covers how to operate it,
its impact, its dependencies and the evidence, what to check around a run and what stays open; the service card
follows them.

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
  tag reaches the included tasks: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)
- **Risks:** [R2](../risk/risk-register.md#r2); [R25](../risk/risk-register.md#r25) does not apply to 2024.1 (the
  risk register keeps the entry and says why)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components) (row "Fluentd"), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)
- **Image registry, new in 2024.1:** with `enable_fluentd` on (default `yes`, `group_vars/all.yml:765`), the config
  step runs `kolla_container` `ensure_image` on the fluentd image, which pulls it when it is not on the host
  (`roles/common/tasks/config.yml:42-51`; `module_utils/kolla_docker_worker.py:501-503`,
  `module_utils/kolla_podman_worker.py:675-677`), then reads its labels with `docker_image_info` or
  `podman_image_info` (`config.yml:53-91`), modules of the `community.docker` and `containers.podman` collections
  (ansible-core 2.16.20 `lib/ansible/config/ansible_builtin_runtime.yml:61-62,733-734`; `requirements-core.yml:18-23`)
  [CODE].

### Evidence

- **Fact sheet:** – (see [Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard), which also records that the
  `common_run` guard is gone)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `fluentd`, `cron`,
  `kolla-toolbox`)
- **Also:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md); handlers:
  [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### What changed in 2024.1

Read in the 2024.1 sources and compared with 2023.1 [CODE]:

| Item | 2024.1 | Evidence |
|---|---|---|
| Play | Same hosts, tag and `serial`; new `max_fail_percentage`, `common_max_fail_percentage`, then `kolla_max_fail_percentage`, then 100 | `site.yml:88-103` |
| fluentd command and user | Read from the image labels `fluentd_binary` and `fluentd_user`, `td-agent` when a label is missing; the 2024.1 kolla image sets both to `fluentd`. The command is now `<fluentd_cmd> -c /etc/<cmd>/<cmd>.conf -o …`, and `td-agent.conf` is copied to `/etc/<cmd>/<cmd>.conf`. In 2023.1 the template hard-coded `td-agent` | `roles/common/tasks/config.yml:53-91`; `roles/common/templates/fluentd.json.j2:1-12`; kolla `docker/fluentd/Dockerfile.j2:3,6` |
| fluentd read positions | `pos_file /var/run/<fluentd_user>/…` instead of `/var/run/td-agent/…`; the image creates `/var/run/fluentd` | `roles/common/templates/conf/input/00-global.conf.j2:12`; kolla `docker/fluentd/Dockerfile.j2:41-42` |
| fluentd volumes | Always mounts `/var/log/journal:/var/log/journal:ro`, whatever `enable_fluentd_systemd` says | `roles/common/defaults/main.yml:118-124` |
| New fluentd inputs | `11-letsencrypt.conf.j2` with `enable_letsencrypt`; `12-systemd.conf.j2` (the journal) with `enable_fluentd_systemd`, which defaults to `enable_fluentd` and `enable_central_logging` (default `no`); OVN log files with `enable_ovn`, on the OVN hosts only | `roles/common/tasks/config.yml:166-169`; `group_vars/all.yml:747,766`; `roles/common/templates/conf/input/10-openvswitch.conf.j2:31-67` |
| fluentd outputs | `bulk_message_request_threshold` (`20M`) and `chunk_limit_size` (`8M`) on the Elasticsearch and OpenSearch outputs | `roles/common/defaults/main.yml:147,152`; `roles/common/templates/conf/output/01-es.conf.j2:27-33` |
| kolla_toolbox | Command `kolla_toolbox` instead of `sleep infinity`: a `sleep 1` loop that exits 0 on TERM or QUIT. `/run` is mounted `:shared` only with Docker, plus `run_default_volumes_<engine>` (empty for Docker). The image ships `ansible-core==2.16.*` | `roles/common/templates/kolla-toolbox.json.j2:2`; kolla `docker/kolla-toolbox/kolla_toolbox.sh:3-16`, `docker/kolla-toolbox/Dockerfile.j2:76`; `roles/common/defaults/main.yml:22,111`; `group_vars/all.yml:165-172` |
| Service lists | fluentd input list: `placement` added; freezer, murano, sahara, senlin and solum gone. Logrotate list: `redis` added; freezer, murano, outward-rabbitmq, sahara, senlin, solum and vitrage gone | `roles/common/defaults/main.yml:154-210`; `roles/common/tasks/config.yml:212-261` |
| Podman | With `kolla_container_engine: podman` only: `/etc/tmpfiles.d/kolla.conf` and `systemd-tmpfiles --create` on the host | `roles/common/tasks/config.yml:30-40` |

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 7 (scope): `-t common` runs the common
  role in its own play, and service tags do not run it (`site.yml:88-103`, `roles/common/tasks/main.yml:2`).
- [R2](../risk/risk-register.md#r2), precautions: treat `enable_*` changes as fleet-wide changes for the `common` play;
  roll out with `--limit` batches or `ANSIBLE_SERIAL` (the play has `serial: kolla_serial`, `site.yml:95`).
- Registry: the run needs the fluentd image of the configured tag on every host of the play, or access to the
  registry to pull it, even for `genconfig` (`roles/common/tasks/config.yml:42-51`) [CODE].
- [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §4](../operations/apply-common-changes.md#4-sequence-risks-and-verification), verification: before, `genconfig`, then
  `kolla_set_configs --check` in each of `fluentd`, `cron` and `kolla_toolbox` (1 in any of them = all three will
  restart, by loop-notify); the check does not cover image, volume or `command` changes. After, `docker ps` shows
  fresh start times, `docker logs fluentd` has no parse errors and logs still reach the configured output.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `common`:
  config files that can change: `config.json`, `td-agent.conf`, the cron logrotate config and the kolla_toolbox files,
  on every host of `common` [CODE] (`roles/common/tasks/config.yml:93-323`); safe on its own: "yes; the way to push
  common config fleet-wide".

### Known limits and open points

- [F2](../reference/findings.md#f2), "`-t common` is a no-op": does not hold in 2024.1. The tag `common` is on the play
  (`site.yml:100-101`), and the tasks of the dynamic include in `roles/common/tasks/main.yml:2` keep the include's
  parent (ansible-core 2.16.20 `lib/ansible/plugins/strategy/__init__.py:831-842`), whose tags extend those of the
  play (`lib/ansible/playbook/block.py:352-361`; `tags` is an `extend=True` field,
  `lib/ansible/playbook/taggable.py:42`) [CODE] ([Apply `common` changes
  §2](../operations/apply-common-changes.md#2-the-tag-does-nothing)). The reverse surprise stays: a tagged service run
  does not apply pending `common` changes, which wait for an untagged run or `-t common`.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": still holds. `Check common containers` loops over
  `common_services` with `notify: "Restart {{ item.key }} container"` (`roles/common/tasks/check-containers.yml:2-17`),
  and so does the `config.json` task (`roles/common/tasks/config.yml:93-102`). In ansible-core 2.16.20 the loop result
  is changed when any item changed (`lib/ansible/executor/task_executor.py:124-130`), every executed item carries the
  notification (`:816-820`), and the strategy saves the notifications of every item of a changed result
  (`lib/ansible/plugins/strategy/__init__.py:648-673`): a change for one container restarts all three on that host
  [CODE].
- [F16](../reference/findings.md#f16): a common container whose systemd unit was written by 2023.1 code is reported as
  changed at its first 2024.1 check, and the fluentd container also differs by its new `/var/log/journal` volume
  (`roles/common/defaults/main.yml:124`) [CODE].
- [Q10](../troubleshooting/open-questions.md#q10) compares Ansible 2.8.20 and 2.9.27 and does not cover
  ansible-core 2.16.20; for 2024.1, F1 and F2 are settled by the code cited in the items above.
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": for `common`, the
  `enable_*` flags of the OpenStack services (`fluentd_input_openstack_services`,
  `roles/common/defaults/main.yml:154-210`)
  and the logrotate services list (`roles/common/tasks/config.yml:212-261`) end up in `td-agent.conf` and
  `logrotate.conf` on every common host [CODE]. New flags in 2024.1:
  - `enable_redis` (default `no`, `group_vars/all.yml:840`) changes `logrotate.conf` on every cron host
    (`config.yml:254`), not `td-agent.conf` (redis is not in the fluentd list). The Octavia precheck requires it when
    the jobboard is on (`roles/octavia/tasks/precheck.yml:67-72`), and the jobboard is on by default with Octavia and
    the amphora driver (`group_vars/all.yml:832`);
  - `enable_letsencrypt` (default `no`, `group_vars/all.yml:796`) adds the `11-letsencrypt.conf.j2` input to
    `td-agent.conf` on every fluentd host (`config.yml:166-167`). A `cron-logrotate-letsencrypt.conf.j2` template
    exists, but `letsencrypt` is not in the logrotate list (`config.yml:212-261`), so it is never rendered;
  - `enable_ovn` (`group_vars/all.yml:834`) adds OVN log inputs to `td-agent.conf`, but only on the hosts of the
    `ovn-controller`, `ovn-nb-db`, `ovn-northd` and `ovn-sb-db` groups
    (`roles/common/templates/conf/input/10-openvswitch.conf.j2:31-67`).
- OVN read positions: the OVN inputs write their positions to `/var/run/fluentd/`, hard-coded, while every other input
  uses `/var/run/<fluentd_user>/` (`roles/common/templates/conf/input/10-openvswitch.conf.j2:36,54`, `:4,19`). With the
  2024.1 image both are `/var/run/fluentd` (kolla `docker/fluentd/Dockerfile.j2:3,41-42`); with an image whose labels
  are missing, `fluentd_user` falls back to `td-agent` (`roles/common/tasks/config.yml:65-71`) and the two paths differ
  [CODE]. What fluentd then does is [NOT AVAILABLE].
- [What is not known](../troubleshooting/what-is-not-known.md#running-vms-and-compute-hosts): the sources do not
  establish whether restarts that touch none of the containers the study traces to running VMs (the `common` containers,
  the control-plane services) affect running VMs, APIs or traffic another way.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour),
  row "fluentd": the sources do not establish whether the tail read positions (in `/var/run/fluentd/` with the 2024.1
  image, on no volume, `roles/common/templates/conf/input/00-global.conf.j2:12`,
  `roles/common/defaults/main.yml:118-124`)
  survive a config-only restart, and whether they are lost on a recreate.
- Journal input: with `enable_fluentd_systemd`, `config.json` asks `kolla_set_configs` to chown `/var/log/journal`
  recursively to the fluentd user (`roles/common/templates/fluentd.json.j2:27-33`), while the volume is mounted
  read-only (`roles/common/defaults/main.yml:124`). A failed chown is logged and does not stop the start (kolla
  `docker/base/set_configs.py:351-355`) [CODE]; whether fluentd can then read the journal is [NOT AVAILABLE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 9: a changed `rabbitmq_cluster_cookie`
  recreates the brokers but their cookie file keeps the old value, while `kolla_toolbox` gets the new one
  [CODE; consequences NOT AVAILABLE].

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py common -->

| Item | Value |
|---|---|
| Play | site.yml:88 |
| Tags | common |
| Play host patterns | cron, fluentd, kolla-logs, kolla-toolbox |
| Node types in play (example inventory) | compute, control, monitoring, network, storage |
| Node types running its containers | compute, control, monitoring, network, storage |
| Containers | `fluentd`, `kolla_toolbox`, `cron` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → bootstrap → flush handlers |
| Task files | bootstrap.yml, check-containers.yml, check.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `admin-openrc-system.sh.j2`, `admin-openrc.sh.j2`, `clouds.yaml.j2`, `conf/filter/00-record_transformer.conf.j2`, `conf/filter/01-rewrite.conf.j2`, `conf/filter/02-parser.conf.j2`, `conf/format/apache_access.conf.j2`, `conf/format/wsgi_access.conf.j2`, `conf/input/00-global.conf.j2`, `conf/input/01-syslog.conf.j2`, `conf/input/02-mariadb.conf.j2`, `conf/input/03-rabbitmq.conf.j2`, `conf/input/04-openstack-wsgi.conf.j2`, `conf/input/05-libvirt.conf.j2`, `conf/input/08-prometheus.conf.j2`, `conf/input/10-openvswitch.conf.j2`, `conf/input/11-letsencrypt.conf.j2`, `conf/input/12-systemd.conf.j2`, `conf/output/00-local.conf.j2`, `conf/output/01-es.conf.j2`, `conf/output/03-opensearch.conf.j2`, `cron-logrotate-ansible.conf.j2`, `cron-logrotate-aodh.conf.j2`, `cron-logrotate-barbican.conf.j2`, `cron-logrotate-blazar.conf.j2` … (+57) |
| Handlers (definition order) | Restart fluentd container; Restart kolla-toolbox container; Initializing toolbox container using normal user; Restart cron container |
| Key variables | `enable_fluentd`, `enable_* (all, via td-agent/logrotate)`, `elasticsearch_address`, `enable_monasca` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md) — the commands that
  push `common` changes, what restarts and how to verify
- [Chrony](chrony.md) — `-t chrony`, the Ussuri way to push `common` changes; no chrony role or play in 2024.1
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — the tag semantics that make
  `-t common` work in 2024.1
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common_run` guard (gone since 2023.1) and the global `fluentd` and `cron` configs
- [Findings F16](../reference/findings.md#f16) — the first 2024.1 check of a container whose unit 2023.1 wrote
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host
- [Components](index.md) — the other component pages
