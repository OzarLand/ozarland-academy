---
title: Apply common changes (fluentd, cron, kolla_toolbox)
description: How -t common reconfigure reaches every host through the standalone common play in 2024.1, which runs bring common along, what restarts and how to verify.
tags: [fluentd, cron, kolla-toolbox, common, reconfigure, tags, loop-notify, kolla-set-configs]
impact: [restarts-on-drift]
---

# Apply `common` changes (fluentd, cron, kolla_toolbox)

How to push changes of the `common` role (fluentd, cron, kolla_toolbox) to hosts. In 2024.1 `common` is still a play
of its own, tagged `common`, so `-t common reconfigure` reconfigures every host of the `common` group. New in 2024.1,
the role's config step first makes sure the fluentd image is on each host and reads its labels.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **`-t common reconfigure` reconfigures every common host** [CODE] ([§2](#2-the-tag-does-nothing)). `common` reaches
>   a
>   host only through the "Apply role common" play: a run without tags, or a run whose tags include `common`
>   ([§3](#3-how-common-actually-reaches-hosts)). `-t nova` or `-t neutron` do not bring it along.
> - **New in 2024.1: the config step can pull the fluentd image** [CODE]. With `enable_fluentd` on, every run of the
>   role, `genconfig` included, runs `ensure_image` on the fluentd image and reads its labels to choose the fluentd
>   command and user ([§3](#3-how-common-actually-reaches-hosts)).

> [!WARNING]
> [R2](../risk/risk-register.md#r2): fleet-wide restarts after an `enable_*` change — see "Hidden coupling" in
> [§3](#3-how-common-actually-reaches-hosts). In 2024.1, `enable_redis`, `enable_letsencrypt` and `enable_ovn` join
> the flags that change the common configs.

## 1. Commands

### 1.1 Apply `common` changes (fluentd, cron, kolla_toolbox)

```bash
# 2024.1: common is its own play, tagged common (site.yml:88-103)
kolla-ansible -i multinode -t common reconfigure
kolla-ansible -i multinode -t common reconfigure --limit 'compute[0:49]'
```

- The play targets the groups `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`, all children of `common`
  (control, network, compute, storage, monitoring) in the shipped inventory [CODE] (`site.yml:88-103`;
  `inventory/multinode:49-54`, `:203-213`). It runs with `serial: kolla_serial` (`site.yml:95`), so `ANSIBLE_SERIAL`
  batches it (`tools/kolla-ansible:531`). New in 2024.1, the play also sets `max_fail_percentage` from
  `common_max_fail_percentage`, then `kolla_max_fail_percentage`, then 100 (`site.yml:96-99`); with the default 100 it
  never stops the play early ([Controlled batches](controlled-batches.md)).
- The `chrony` tag used for this in Ussuri does not exist: there is no `chrony` role or play in 2024.1 (no
  `roles/chrony`, no `chrony` in `site.yml`).
- **Registry:** with `enable_fluentd` on (default `yes`, `group_vars/all.yml:765`), the run needs the fluentd image of
  the configured tag on each host of the play, or the registry to pull it (`roles/common/tasks/config.yml:42-51`).

## 2. The tag does nothing

Still not true in 2024.1. `roles/common/tasks/main.yml:1-2` is a bare `include_tasks: "{{ kolla_action }}.yml"` with
no tag and no `common_run` guard; the tag `common` is set on the play (`site.yml:100-101`). The tasks of a dynamic
include keep the include's parent block (ansible-core 2.16.20 `lib/ansible/plugins/strategy/__init__.py:831-842`), a
block extends its tags with those of its play (`lib/ansible/playbook/block.py:352-361`; `tags` is an `extend=True`
field, `lib/ansible/playbook/taggable.py:42`), and the included block is then filtered by tag
(`lib/ansible/plugins/strategy/linear.py:272`). The included `reconfigure.yml` tasks therefore carry `common` and run
[CODE]. Tag semantics: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code).

## 3. How `common` actually reaches hosts

- **Where it runs:** the `common` role (fluentd, cron, kolla_toolbox) runs only in the "Apply role common" play, on the
  hosts of `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` [CODE] (`site.yml:88-103`). No role declares `common` as
  a dependency (no `roles/*/meta` directory in 2024.1), and there is no `common_run` guard.

  | Command | Hosts that get `common` |
  |---|---|
  | `reconfigure` (no tag) | all hosts of the `common` group, in the common play (the first play after the prechecks play, `site.yml:77-103`) |
  | `-t nova` | none: the nova plays (`nova.yml:103-150`) do not include the `common` role [CODE] |
  | `-t neutron` | none (same reason) |
  | `-t chrony` | none: no play carries the tag in 2024.1, only the `always`-tagged plays (fact gathering, host grouping) run |
  | `-t haproxy` | none: the loadbalancer play (`site.yml:105-326`) does not include `common` |
  | `-t common` | all hosts of the `common` group (recommended way to push `common` changes) |
- **What it can change:**
  - **new in 2024.1, before any file:** the fluentd image. `Ensure fluentd image is present for label check` runs
    `kolla_container` `ensure_image`, which pulls the image only when it is absent
    (`roles/common/tasks/config.yml:42-51`; `module_utils/kolla_docker_worker.py:501-503`,
    `module_utils/kolla_podman_worker.py:675-677`). Its condition is `enable_fluentd` alone, so it runs on every host
    of the play. The labels `fluentd_binary` and `fluentd_user` are then read with `docker_image_info` or
    `podman_image_info` and set the facts `fluentd_cmd` and `fluentd_user`, `td-agent` when a label is missing
    (`config.yml:53-91`). The 2024.1 kolla image sets both labels to `fluentd` (kolla
    `docker/fluentd/Dockerfile.j2:3,6`);
  - `config.json` of the three containers (`config.yml:93-102`). fluentd's command is now
    `<fluentd_cmd> -c /etc/<fluentd_cmd>/<fluentd_cmd>.conf -o /var/log/kolla/fluentd/fluentd.log`, and `td-agent.conf`
    is copied to that path (`roles/common/templates/fluentd.json.j2:1-12`). kolla_toolbox's command is now
    `kolla_toolbox` instead of `sleep infinity` (`roles/common/templates/kolla-toolbox.json.j2:2`);
  - `td-agent.conf` (fluentd inputs/outputs). It is built from `fluentd_input_openstack_services` (the `enable_*`
    flags of the OpenStack services, `roles/common/defaults/main.yml:154-210`) read by
    `conf/input/00-global.conf.j2:2-5`; the input files enabled by `enable_nova`/`enable_nova_libvirt_container`,
    `enable_prometheus_fluentd_integration`, and, new in 2024.1, `enable_letsencrypt` and `enable_fluentd_systemd`
    (the journal) (`config.yml:149-169`); the OVN log inputs when `enable_ovn`, on the OVN hosts only
    (`roles/common/templates/conf/input/10-openvswitch.conf.j2:31-67`); the local syslog outputs of
    `syslog_facilities` (swift and haproxy, and the glance and neutron TLS proxies, each only on its own hosts,
    `roles/common/defaults/main.yml:82-104`); the Elasticsearch (`elasticsearch_address` defined) and OpenSearch
    (`enable_opensearch` or an external `opensearch_address`) outputs, now with `bulk_message_request_threshold` and
    `chunk_limit_size` (`roles/common/defaults/main.yml:147,152`); and custom files under
    `{{ node_custom_config }}/fluentd/` [CODE] (`roles/common/tasks/config.yml:104-203`);
  - `logrotate.conf` (cron, built from `cron_logrotate_services`, task at `roles/common/tasks/config.yml:205-270`);
  - the RabbitMQ Erlang cookie, `rabbitmq-env.conf` and `erl_inetrc` in kolla_toolbox (only with `enable_rabbitmq`,
    `config.yml:272-323`);
  - with Podman only, `/etc/tmpfiles.d/kolla.conf` on the host, followed by `systemd-tmpfiles --create`
    (`config.yml:30-40`);
  - container definitions of fluentd, cron and kolla_toolbox (image tag, volumes, environment, dimensions). New in
    2024.1, fluentd always mounts `/var/log/journal:/var/log/journal:ro` (`roles/common/defaults/main.yml:124`), and
    kolla_toolbox mounts `/run` with `:shared` only under Docker, plus `run_default_volumes_<engine>`
    (`roles/common/defaults/main.yml:22,111`; `group_vars/all.yml:165-172`).
- **What restarts:** any drift restarts **all three** containers on that host (loop-notify in `check-containers.yml`)
  [CODE] (`roles/common/tasks/check-containers.yml:2-17`, `compare_container` with a looped
  `notify: "Restart {{ item.key }} container"`; ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:124-130`,
  `lib/ansible/plugins/strategy/__init__.py:648-673`;
  [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). The
  `config.json` task is looped with the same `notify` (`roles/common/tasks/config.yml:93-102`).
  - **First 2024.1 run after 2023.1:** a container that no 2024.1 run has recreated or restarted yet is reported as
    changed by its
    unit file ([F16](../reference/findings.md#f16)); for fluentd, the new journal volume also makes the container
    differ (`roles/common/defaults/main.yml:124`), so it is recreated [CODE].
  - A change of `config.json`'s `command` alone (e.g. kolla_toolbox's) is not seen by `kolla_set_configs --check`
    ([Kolla images §3.2](../concepts/kolla-images.md#32-what-is-never-compared)). A change of the fluentd command
    from the labels also moves the destination of `td-agent.conf` (`fluentd.json.j2:8-9`), which the check reports as a
    missing destination ([Kolla images §3.3](../concepts/kolla-images.md#33-exit-codes)) [CODE].
- **Impact:**
  - fluentd: log shipping gap. The Elasticsearch and OpenSearch outputs buffer to files under `/var/lib/fluentd/data`,
    the `fluentd_data` volume, which a restart or a recreate keeps (`roles/common/defaults/main.yml:123`;
    `roles/common/templates/conf/output/01-es.conf.j2:28-33`, `03-opensearch.conf.j2:28-33`). The tail read positions
    are in `/var/run/<fluentd_user>/`, `/var/run/fluentd/` with the 2024.1 image, on no volume
    (`roles/common/templates/conf/input/00-global.conf.j2:12`; kolla `docker/fluentd/Dockerfile.j2:41-42`):
    [NOT AVAILABLE] whether they survive a config-only restart and whether they are lost when the container is recreated
    (e.g. an image or volume change) ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)).
  - cron: log rotation is delayed.
  - kolla_toolbox: no service template references it (only `roles/common/templates/kolla-toolbox.json.j2` names it
    under `roles/*/templates`); Kolla's own tasks use it through the `kolla_toolbox` module, which fails when the
    container is not running (`library/kolla_toolbox.py:150-153`, `:206-216`) [CODE]. Its new command exits 0 on TERM
    or QUIT (kolla `docker/kolla-toolbox/kolla_toolbox.sh:3-16`).
  - **VM and API impact:** [NOT AVAILABLE]. None of the three is a container that [Tags
    §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running
    VMs [CODE].
- **Hidden coupling:** enabling a service that appears in either list (most OpenStack services, e.g. barbican) changes
  `td-agent.conf` and/or `logrotate.conf` on *every* host ([Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard)). New in 2024.1 [CODE]:
  - `enable_redis` changes `logrotate.conf` on every cron host (`roles/common/tasks/config.yml:254`). With Octavia and
    the amphora driver, the jobboard is on by default (`group_vars/all.yml:832`) and the Octavia precheck requires
    `enable_redis` (`roles/octavia/tasks/precheck.yml:67-72`), so enabling Octavia can bring this change along;
  - `enable_letsencrypt` adds an input to `td-agent.conf` on every fluentd host (`config.yml:166-167`); its logrotate
    template is not in the logrotate list (`config.yml:212-261`), so `logrotate.conf` does not change;
  - `enable_ovn` changes `td-agent.conf` only on the hosts of the OVN groups
    (`roles/common/templates/conf/input/10-openvswitch.conf.j2:31-67`).

  The common containers restart on every common host whose file changed at the next run that includes the common
  play: any run without tags, or a run with `-t common`. A tagged run such as `-t nova` does not trigger it
  ([Reconfigure Nova §3](reconfigure-nova.md#3-what-changes-per-type-of-change-code)).

## 4. Sequence, risks and verification

- **Sequence on each reached host**, from `roles/common/tasks/deploy.yml:2-9` (`reconfigure.yml` imports it,
  `roles/common/tasks/reconfigure.yml:2`):
  1. config (`roles/common/tasks/config.yml:2-323`): config directories; CA certificates if
     `kolla_copy_ca_into_containers`; with Podman, the tmpfiles config; **new:** `ensure_image` of the fluentd image,
     then its labels and the `fluentd_cmd`/`fluentd_user` facts; `config.json` ×3; custom fluentd files (found once,
     on the deploy host, `run_once` + `delegate_to: localhost`); `td-agent.conf`; cron `logrotate.conf`; RabbitMQ
     Erlang cookie, `rabbitmq-env.conf` and `erl_inetrc` for kolla_toolbox. `rabbitmq-env.conf` and `erl_inetrc`
     notify no handler (`config.yml:297-323`); a change to them is found by the next step, since both are listed in
     kolla_toolbox's `config.json` (`roles/common/templates/kolla-toolbox.json.j2:10-21`);
  2. check-containers: one looped `compare_container` over fluentd, kolla_toolbox and cron;
  3. bootstrap: `kolla_logs` volume and the `/var/log/kolla` link, now to `container_engine_volumes_path`
     (`roles/common/tasks/bootstrap.yml:1-16`; `group_vars/all.yml:156-158`);
  4. flush handlers, in definition order: Restart fluentd → Restart kolla-toolbox (→ toolbox `ansible --version`
     init, with `kolla_container_engine exec`) → Restart cron (`roles/common/handlers/main.yml:2`, `:18`, `:37-40`,
     `:42`).
- **`genconfig`** (`kolla_action=config`, `tools/kolla-ansible:559`) runs `config.yml` only: no restart, since every
  restart handler carries `when: kolla_action != "config"` (`roles/common/handlers/main.yml:15-16`), but it does run
  `ensure_image` and can pull the fluentd image [CODE].
- **Hosts, parallelism:** all reached hosts at once, unless batched (`serial: kolla_serial`, `site.yml:95`).
- **Interruption:** one stop/start per container. With Docker, a restart goes through the container's systemd unit
  and a recreate stops it through the unit when one exists; the unit's `ExecStop` is `<engine> stop <name> -t
  <graceful_timeout>`, with `docker_graceful_timeout: 60` (`module_utils/kolla_docker_worker.py:415-431`,
  `:439-459`; `module_utils/kolla_systemd_worker.py:32`; `group_vars/all.yml:139,151`; [Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). A recreate
  pulls the image first when it is absent (`module_utils/kolla_docker_worker.py:341-363`). Log shipping pauses, cron
  rotation is delayed, and Kolla's own `kolla_toolbox` tasks fail while the container is not running. [NOT AVAILABLE]
  Whether VMs, APIs, networking or storage are affected ([§3](#3-how-common-actually-reaches-hosts)).
- **Risks:** [R2](../risk/risk-register.md#r2) (fleet-wide restarts after an `enable_*` change),
  [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a reconfigure; in 2024.1 `-t common` does reconfigure,
  see [§2](#2-the-tag-does-nothing)), [F16](../reference/findings.md#f16) (first 2024.1 check after 2023.1).
- **Verification:**
  - before: make sure the fluentd image of the configured tag is on the hosts or reachable in the registry; then
    `genconfig`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check; echo $?` in each of
    `fluentd`, `cron` and `kolla_toolbox` (`podman exec` with Podman; 1 in any of them = all three will restart, by
    loop-notify; a `logrotate.conf`-only change, e.g. toggling `enable_redis`, shows up only in `cron`). The check
    does not cover image, volume, unit-file or `command` changes;
  - after: `docker ps --filter name=fluentd --filter name=cron --filter name=kolla_toolbox` shows fresh start times;
    `docker logs fluentd` has no parse errors; logs still reach the configured output.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R2](../risk/risk-register.md#r2) (fleet-wide
  restarts after an `enable_*` change) and [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a
  reconfigure)
- [Common: fluentd, cron, kolla_toolbox](../components/common.md) — service card and where to look
- [Chrony](../components/chrony.md) — the Ussuri tag used to push `common` changes; the role does not exist in 2024.1
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Controlled batches](controlled-batches.md) — `genconfig` first, then batches; `max_fail_percentage`
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — dynamic `include_tasks` and tag
  inheritance: the tag semantics behind §2
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common` role and the `common_run` guard (gone since 2023.1)
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) —
  `enable_<new service>: yes` changes fluentd/logrotate on every host
