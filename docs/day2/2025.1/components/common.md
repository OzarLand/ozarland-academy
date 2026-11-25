---
title: "Common: fluentd, cron, kolla_toolbox"
description: "Where the 2025.1 study covers the common role (fluentd, cron, kolla_toolbox): its own play, the -t common tag, how changes reach hosts, risks."
tags: [fluentd, cron, kolla-toolbox, tags, kolla-set-configs, risk, dependencies, bugs, unknowns]
---

# Common: fluentd, cron, kolla_toolbox

This page is the starting point for the `common` role: the containers `fluentd`, `kolla_toolbox` and `cron`, on the
compute, control, monitoring, network and storage nodes of the example inventory. In 2025.1 the role is still no meta
dependency of any other role (no `roles/*/meta` directory): it runs only in its own play, "Apply role common", on the
groups `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`, with the play tag `common` (`site.yml:88-103`). `-t common`
therefore runs it, and a service tag such as `-t nova` does not [CODE]. **Changed in 2025.1** [CODE]: the 2024.1 step
that pulled the fluentd image and read its labels during the config step is gone; the fluentd command, file names and
user are fixed to `fluentd` (`roles/common/templates/fluentd.json.j2:2-8`). The config step now also writes
`/etc/systemd/system/kolla.target` on every host of the play (`roles/common/tasks/config.yml:54-58`), and the restart
decision moved to the shared `service-check-containers` role. The lists below say where the study covers how to
operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the service
card follows them.

## Where to look

### Operate

- **Scenario:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md)
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox):
  `kolla-ansible reconfigure -i multinode -t common`, optionally with `--limit` (2024.1 form:
  `kolla-ansible -i multinode -t common reconfigure`)

### Impact and risk

- **What the tag executes (`common`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `common`; why
  the
  tag reaches the included tasks: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)
- **Risks:** [R2](../risk/risk-register.md#r2); [R25](../risk/risk-register.md#r25) does not apply to 2025.1 (the risk register keeps the entry and says why)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §2](dependencies.md#2-infrastructure-components) (row "Fluentd"), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)
- **Image registry, changed in 2025.1:** the config step no longer touches the image. 2024.1 ran `kolla_container`
  `ensure_image` on the fluentd image and read its labels with `docker_image_info` or `podman_image_info`; 2025.1 has
  neither task (`roles/common/tasks/config.yml:1-289`), so `genconfig` and `-t common` need no registry access. The
  image is pulled by `pull`, or by the container creation of `deploy` [CODE].
- **CA certificates, new in 2025.1:** with `kolla_copy_ca_into_containers`, the `config.json` of all three containers
  copies `/etc/kolla/<container>/ca-certificates` into `/var/lib/kolla/share/ca-certificates`
  (`roles/common/templates/cron.json.j2:10-16`, `fluentd.json.j2:9-15`, `kolla-toolbox.json.j2:21-27`), which the
  container's start script installs ([Kolla images §2.4](../concepts/kolla-images.md#24-kolla_copy_cacerts-and-kolla_httpd_setup))
  [CODE].

### Evidence

- **Fact sheet:** – (see [Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard), which also records that the
  `common_run` guard is gone)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `fluentd`, `cron`,
  `kolla-toolbox`)
- **Also:** [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md); handlers:
  [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### What changed in 2025.1

Read in the 2025.1 sources and compared with 2024.1 [CODE]:

| Item | 2025.1 | Evidence |
|---|---|---|
| Restart decision | The config tasks notify no handler; `check-containers.yml` imports `service-check-containers`, which notifies only the handlers of the containers that `compare_container` reports changed. The handlers lost their `kolla_action != "config"` guard | `roles/common/tasks/check-containers.yml:2-3`; `roles/common/tasks/config.yml:60-66`, `:104-169`; `roles/service-check-containers/tasks/main.yml:4-41`; `roles/common/handlers/main.yml:2-50` |
| fluentd image labels | No `ensure_image`, no image label read: the command is `fluentd -c /etc/fluentd/fluentd.conf -o /var/log/kolla/fluentd/fluentd.log` and the owner of every path is `fluentd`. The rendered file is `fluentd.conf` (2024.1: `td-agent.conf`) | `roles/common/templates/fluentd.json.j2:2-8, :26, :33`; `roles/common/tasks/config.yml:104-169`; kolla `docker/fluentd/Dockerfile.j2:3, :6` |
| fluentd read positions | `pos_file /var/run/fluentd/…` in every input (2024.1: `/var/run/<fluentd_user>/…`) | `roles/common/templates/conf/input/00-global.conf.j2:13`; `10-openvswitch.conf.j2:4, :19` |
| New fluentd inputs | `13-uwsgi.conf.j2` (always: the `*-uwsgi.log` files of the enabled OpenStack services, which `00-global` now excludes), `14-valkey.conf.j2` with `enable_valkey`; OVN SB relay logs on `ovn-sb-db-relay` hosts. `enable_watch_timer` is now the variable `fluentd_enable_watch_timer` (default `"false"`, as before) | `roles/common/tasks/config.yml:134-137`; `roles/common/templates/conf/input/13-uwsgi.conf.j2:5-6`; `00-global.conf.j2:12`; `10-openvswitch.conf.j2:67-84`; `roles/common/defaults/main.yml:132` |
| fluentd outputs | Elasticsearch and OpenSearch outputs gain a second `<match retry_es>` / `<match retry_os>` block with its own buffer path, and the main block sets `retry_tag` | `roles/common/templates/conf/output/01-es.conf.j2:1-44`, `03-opensearch.conf.j2:1-44` |
| Logrotate | `logrotate.conf` can be overridden per host or globally (`<node_custom_config>/cron/[<host>/]cron-logrotate-global.conf`); new entries `valkey` and `opensearch-dashboards` (split from `opensearch`); `swift` gone | `roles/common/tasks/config.yml:171-239` |
| `kolla.target` | Written on every host of the play, from `kolla.target.j2`; every container unit is `PartOf=kolla.target` ([F16](../reference/findings.md#f16)). Nothing enables or starts the target | `roles/common/tasks/config.yml:54-58` |
| EL10 hosts | `/var/log/journal` created (`root:systemd-journal`, `2755`) when the base distro is CentOS Stream 10 or Rocky 10 | `roles/common/tasks/config.yml:30-40` |
| kolla_toolbox | Same `kolla_toolbox` sleep loop; the image ships `ansible-core==2.18.*` (2024.1: 2.16) | kolla `docker/kolla-toolbox/kolla_toolbox.sh:3-16`, `docker/kolla-toolbox/Dockerfile.j2:107` |
| Image names | `docker_image_name_prefix` added to the three image names | `roles/common/defaults/main.yml:65, :69, :73` |

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 7 (scope): `-t common` runs the common
  role in its own play, and service tags do not run it (`site.yml:88-103`, `roles/common/tasks/main.yml:2`).
- [R2](../risk/risk-register.md#r2), precautions: treat `enable_*` changes as fleet-wide changes for the `common` play;
  roll out with `--limit` batches or `deploy -e kolla_serial=N` (the play has `serial: kolla_serial`, `site.yml:95`;
  `reconfigure` forces `kolla_serial=0`, [F19](../reference/findings.md#f19)).
- Registry: **changed in 2025.1**, `genconfig` and the config step no longer need the fluentd image or the registry
  ([Dependencies](#dependencies)) [CODE].
- [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §4](../operations/apply-common-changes.md#4-sequence-risks-and-verification), verification: before, `genconfig`, then
  `kolla_set_configs --check` in each of `fluentd`, `cron` and `kolla_toolbox`; a 1 in one of them restarts that
  container only (loop-notify is gone, [F1](../reference/findings.md#f1)). The check now covers the `command` as well,
  but not the image or the volumes, which `compare_container` compares itself. After, `docker ps` shows fresh start
  times, `docker logs fluentd` has no parse errors and logs still reach the configured output.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `common`:
  config files that can change: `config.json`, `fluentd.conf`, the cron `logrotate.conf` and the kolla_toolbox files,
  on every host of `common` [CODE] (`roles/common/tasks/config.yml:60-289`); safe on its own: "yes; the way to push
  common config fleet-wide".
- **First 2025.1 run after the upgrade** [CODE]: the fluentd `config.json` changes source file (`fluentd.conf` instead
  of `td-agent.conf`, `roles/common/templates/fluentd.json.j2:5-6`), and the systemd unit text of every container
  changed ([F16](../reference/findings.md#f16)), so all three common containers restart at their first 2025.1 check,
  on every host of the play at once unless batched. The `td-agent.conf` written by 2024.1 stays in
  `/etc/kolla/fluentd/`; no task removes it.

### Known limits and open points

- [F2](../reference/findings.md#f2), "`-t common` is a no-op": does not hold in 2025.1. The tag `common` is on the play
  (`site.yml:100-101`), and the tasks of the dynamic include in `roles/common/tasks/main.yml:2` inherit it (ansible-core
  2.18.20 `lib/ansible/playbook/block.py:309-359`; `tags` is an extending field, `lib/ansible/playbook/taggable.py:40`)
  [CODE] ([Apply `common` changes §2](../operations/apply-common-changes.md#2-the-tag-does-nothing)). The reverse
  surprise stays: a tagged service run does not apply pending `common` changes, which wait for an untagged run or
  `-t common`.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": **no longer holds in 2025.1**. A change for one common
  container restarts that container only (`roles/service-check-containers/tasks/main.yml:34-41`) [CODE].
- [F16](../reference/findings.md#f16): a common container whose systemd unit was written by 2024.1 code is reported as
  changed at its first 2025.1 check; with Docker on Debian or Ubuntu the new default `nofile` ulimit recreates it
  [CODE].
- [Q10](../troubleshooting/open-questions.md#q10) compares Ansible 2.8.20 and 2.9.27 and does not cover
  ansible-core 2.18.20; for 2025.1, F1 and F2 are settled by the code cited in the items above.
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": for `common`, the
  `enable_*` flags of the OpenStack services (`fluentd_input_openstack_services`,
  `roles/common/defaults/main.yml:146-201`) and the logrotate services list (`roles/common/tasks/config.yml:178-228`)
  end up in `fluentd.conf` and `logrotate.conf` on every common host [CODE]. Flags worth knowing in 2025.1:
  - `enable_valkey` (default `no`, `group_vars/all.yml:965`) adds the valkey input to `fluentd.conf` on every fluentd
    host and the valkey entry to `logrotate.conf` on every cron host (`roles/common/tasks/config.yml:136-137`, `:225`).
    The Octavia jobboard (on by default with Octavia and the amphora driver, `group_vars/all.yml:950`) needs Redis or
    Valkey (`roles/octavia/tasks/precheck.yml:68-71`), so enabling Octavia's jobboard backend changes the common files
    on every host;
  - `enable_redis` (default `no`, `group_vars/all.yml:959`) still changes `logrotate.conf` on every cron host
    (`roles/common/tasks/config.yml:221`);
  - `enable_letsencrypt` (default `no`, `group_vars/all.yml:913`) adds the `11-letsencrypt.conf.j2` input to
    `fluentd.conf` on every fluentd host (`roles/common/tasks/config.yml:130-131`). A `cron-logrotate-letsencrypt.conf.j2`
    template exists, but `letsencrypt` is still not in the logrotate list (`:178-228`), so it is never rendered;
  - `enable_ovn` (`group_vars/all.yml:952`) adds OVN log inputs to `fluentd.conf`, but only on the hosts of the
    `ovn-controller`, `ovn-nb-db`, `ovn-northd`, `ovn-sb-db` and `ovn-sb-db-relay` groups
    (`roles/common/templates/conf/input/10-openvswitch.conf.j2:31-85`).
- The 2024.1 point on OVN read positions is gone: every input now writes its positions under `/var/run/fluentd/`
  [CODE].
- [What is not known](../troubleshooting/what-is-not-known.md#running-vms-and-compute-hosts): the sources do not
  establish whether restarts that touch none of the containers the study traces to running VMs (the `common` containers,
  the control-plane services) affect running VMs, APIs or traffic another way.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour),
  row "fluentd": the sources do not establish whether the tail read positions (in `/var/run/fluentd/`, on no volume,
  `roles/common/templates/conf/input/00-global.conf.j2:13`, `roles/common/defaults/main.yml:110-116`) survive a
  config-only restart, and whether they are lost on a recreate.
- Journal input: with `enable_fluentd_systemd`, `config.json` asks `kolla_set_configs` to chown `/var/log/journal`
  recursively to `fluentd` (`roles/common/templates/fluentd.json.j2:30-36`), while the volume is mounted read-only
  (`roles/common/defaults/main.yml:116`). A failed chown is logged and does not stop the start (kolla
  `docker/base/set_configs.py:365-369`) [CODE]; whether fluentd can then read the journal is [NOT AVAILABLE].
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
| Templates | `admin-openrc-system.sh.j2`, `admin-openrc.sh.j2`, `clouds.yaml.j2`, `conf/filter/00-record_transformer.conf.j2`, `conf/filter/01-rewrite.conf.j2`, `conf/filter/02-parser.conf.j2`, `conf/format/apache_access.conf.j2`, `conf/format/wsgi_access.conf.j2`, `conf/input/00-global.conf.j2`, `conf/input/01-syslog.conf.j2`, `conf/input/02-mariadb.conf.j2`, `conf/input/03-rabbitmq.conf.j2`, `conf/input/04-openstack-wsgi.conf.j2`, `conf/input/05-libvirt.conf.j2`, `conf/input/08-prometheus.conf.j2`, `conf/input/10-openvswitch.conf.j2`, `conf/input/11-letsencrypt.conf.j2`, `conf/input/12-systemd.conf.j2`, `conf/input/13-uwsgi.conf.j2`, `conf/input/14-valkey.conf.j2`, `conf/output/00-local.conf.j2`, `conf/output/01-es.conf.j2`, `conf/output/03-opensearch.conf.j2`, `cron-logrotate-ansible.conf.j2`, `cron-logrotate-aodh.conf.j2` … (+62) |
| Handlers (definition order) | Restart fluentd container; Restart kolla-toolbox container; Initializing toolbox container using normal user; Restart cron container |
| Key variables | `enable_fluentd`, `enable_* (all, via td-agent/logrotate)`, `elasticsearch_address`, `enable_monasca` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md) — the commands that
  push `common` changes, what restarts and how to verify
- [Chrony](chrony.md) — `-t chrony`, the Ussuri way to push `common` changes; no chrony role or play in 2025.1
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — the tag semantics that make
  `-t common` work in 2025.1
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common_run` guard (gone since 2023.1) and the global `fluentd` and `cron` configs
- [Findings F16](../reference/findings.md#f16) — the first 2025.1 check of a container whose unit 2024.1 wrote
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) — `enable_<new service>: yes`
  changes fluentd/logrotate on every host
- [Components](index.md) — the other component pages
