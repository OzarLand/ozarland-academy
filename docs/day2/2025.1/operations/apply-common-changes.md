---
title: Apply common changes (fluentd, cron, kolla_toolbox)
description: How -t common reconfigure reaches every host through the standalone common play in 2025.1, which runs bring common along, what restarts and how to verify.
tags: [fluentd, cron, kolla-toolbox, common, reconfigure, tags, kolla-set-configs]
impact: [restarts-on-drift]
---

# Apply `common` changes (fluentd, cron, kolla_toolbox)

How to push changes of the `common` role (fluentd, cron, kolla_toolbox) to hosts. In 2025.1 `common` is still a play
of its own, tagged `common`, so `-t common reconfigure` reconfigures every host of the `common` group. Changed in
2025.1: the config step no longer touches the fluentd image, and a change restarts only the container it concerns.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **`reconfigure -t common` reconfigures every common host** [CODE] ([§2](#2-the-tag-does-nothing)). `common` reaches
>   a host only through the "Apply role common" play: a run without tags, or a run whose tags include `common`
>   ([§3](#3-how-common-actually-reaches-hosts)). `-t nova` or `-t neutron` do not bring it along.
> - **Changed in 2025.1: only the container that differs restarts** [CODE]. The restart decision is the shared
>   `service-check-containers` role, which notifies the handlers of the changed containers only
>   ([§3](#3-how-common-actually-reaches-hosts), [F1](../reference/findings.md#f1)).
> - **Changed in 2025.1: no image pull in the config step** [CODE]. The fluentd `ensure_image` and image-label tasks of
>   2024.1 are gone; `genconfig` needs no registry ([§1.1](#11-apply-common-changes-fluentd-cron-kolla_toolbox)).

> [!WARNING]
> [R2](../risk/risk-register.md#r2): fleet-wide restarts after an `enable_*` change — see "Hidden coupling" in
> [§3](#3-how-common-actually-reaches-hosts). In 2025.1, `enable_valkey` joins the flags that change the common configs
> on every host, and the first run after the upgrade restarts the three common containers everywhere
> ([§4](#4-sequence-risks-and-verification)).

## 1. Commands

### 1.1 Apply `common` changes (fluentd, cron, kolla_toolbox)

```bash
# 2025.1: common is its own play, tagged common (site.yml:88-103)
kolla-ansible reconfigure -i multinode -t common
kolla-ansible reconfigure -i multinode -t common --limit 'compute[0:49]'
# 2024.1 form: kolla-ansible -i multinode -t common reconfigure
```

- The play targets the groups `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`, all children of `common`
  (control, network, compute, storage, monitoring) in the shipped inventory [CODE] (`site.yml:88-103`;
  `inventory/multinode:49-54`, `:202-212`). It runs with `serial: kolla_serial` (`site.yml:95`), but **`reconfigure`
  always passes `kolla_serial=0`** (`kolla_ansible/cli/commands.py:128-141`, [F19](../reference/findings.md#f19)), so
  the play is batched only with `--limit`, or with `deploy -e kolla_serial=N`, which renders and applies the same
  ([F5](../reference/findings.md#f5); [Controlled batches](controlled-batches.md)). The play's `max_fail_percentage`
  comes from `common_max_fail_percentage`, then `kolla_max_fail_percentage`, then 100 (`site.yml:96-99`); with the
  default 100 it never stops the play early.
- The `chrony` tag used for this in Ussuri does not exist: there is no `chrony` role or play in 2025.1 (no
  `roles/chrony`, no `chrony` in `site.yml`).
- **Registry, changed in 2025.1:** the config step no longer pulls or reads the fluentd image
  (`roles/common/tasks/config.yml:1-289` has no `ensure_image` and no image-info task) [CODE]. The image is needed only
  when a container is created or recreated.

## 2. The tag does nothing

Still not true in 2025.1. `roles/common/tasks/main.yml:1-2` is a bare `include_tasks: "{{ kolla_action }}.yml"` with
no tag and no `common_run` guard; the tag `common` is set on the play (`site.yml:100-101`). A block extends its tags
with those of its parents up to the play (ansible-core 2.18.20 `lib/ansible/playbook/block.py:309-359`; `tags` is an
extending field, `lib/ansible/playbook/taggable.py:40`), and the included block is then filtered by tag
(`lib/ansible/plugins/strategy/linear.py:274`). The included `reconfigure.yml` tasks therefore carry `common` and run
[CODE]. Tag semantics: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code).

## 3. How `common` actually reaches hosts

- **Where it runs:** the `common` role (fluentd, cron, kolla_toolbox) runs only in the "Apply role common" play, on the
  hosts of `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` [CODE] (`site.yml:88-103`). No role declares `common` as
  a dependency (no `roles/*/meta` directory in 2025.1), and there is no `common_run` guard.

  | Command | Hosts that get `common` |
  |---|---|
  | `reconfigure` (no tag) | all hosts of the `common` group, in the common play (the first play after the prechecks play, `site.yml:77-103`) |
  | `-t nova` | none: the nova plays (`nova.yml:103-150`) do not include the `common` role [CODE] |
  | `-t neutron` | none (same reason) |
  | `-t chrony` | none: no play carries the tag in 2025.1, only the `always`-tagged plays (fact gathering, host grouping) run |
  | `-t haproxy` | none: the loadbalancer play (`site.yml:105-327`) does not include `common` |
  | `-t common` | all hosts of the `common` group (recommended way to push `common` changes) |
- **What it can change:**
  - `config.json` of the three containers (`roles/common/tasks/config.yml:60-66`). fluentd's command is fixed:
    `fluentd -c /etc/fluentd/fluentd.conf -o /var/log/kolla/fluentd/fluentd.log`, and `fluentd.conf` is copied to
    `/etc/fluentd/fluentd.conf` (`roles/common/templates/fluentd.json.j2:2-8`). New in 2025.1: with
    `kolla_copy_ca_into_containers`, each of the three files copies the CA certificates to
    `/var/lib/kolla/share/ca-certificates` (`roles/common/templates/cron.json.j2:10-16`, `fluentd.json.j2:9-15`,
    `kolla-toolbox.json.j2:21-27`);
  - `fluentd.conf` (fluentd inputs/outputs; `td-agent.conf` in 2024.1). It is built from
    `fluentd_input_openstack_services` (the `enable_*` flags of the OpenStack services,
    `roles/common/defaults/main.yml:146-201`) read by `conf/input/00-global.conf.j2:2-5` and, new in 2025.1,
    `roles/common/templates/conf/input/13-uwsgi.conf.j2:2-5`; the input files enabled by `enable_nova`/`enable_nova_libvirt_container`,
    `enable_prometheus_fluentd_integration`, `enable_letsencrypt`, `enable_fluentd_systemd` (the journal) and, new,
    `enable_valkey` (`roles/common/tasks/config.yml:113-137`); the OVN log inputs when `enable_ovn`, on the OVN hosts
    only, now with the SB relays (`roles/common/templates/conf/input/10-openvswitch.conf.j2:31-85`); the local syslog
    outputs of `syslog_facilities` (haproxy, and the glance and neutron TLS proxies, each only on its own hosts; swift
    is gone, `roles/common/defaults/main.yml:75-96`); the Elasticsearch (`elasticsearch_address` defined) and
    OpenSearch (`enable_opensearch` or an external `opensearch_address`) outputs, with `bulk_message_request_threshold`
    and `chunk_limit_size` (`roles/common/defaults/main.yml:139, :144`) and, new, a retry block per output; and custom
    files under `{{ node_custom_config }}/fluentd/` [CODE] (`roles/common/tasks/config.yml:68-169`);
  - `logrotate.conf` (cron, built from `cron_logrotate_services`, task at `roles/common/tasks/config.yml:171-239`).
    New in 2025.1: a file at `{{ node_custom_config }}/cron/<host>/cron-logrotate-global.conf` or
    `{{ node_custom_config }}/cron/cron-logrotate-global.conf` replaces the template (`:236-239`);
  - the RabbitMQ Erlang cookie, `rabbitmq-env.conf` and `erl_inetrc` in kolla_toolbox (only with `enable_rabbitmq`,
    `config.yml:241-289`);
  - with Podman only, `/etc/tmpfiles.d/kolla.conf` on the host, followed by `systemd-tmpfiles --create`
    (`config.yml:42-52`);
  - new in 2025.1, on every host: `/etc/systemd/system/kolla.target` (`config.yml:54-58`), and on CentOS Stream 10 or
    Rocky 10 the host directory `/var/log/journal` (`config.yml:30-40`);
  - container definitions of fluentd, cron and kolla_toolbox (image tag, volumes, environment, dimensions). fluentd
    mounts `/var/log/journal:/var/log/journal:ro` (`roles/common/defaults/main.yml:116`); kolla_toolbox mounts `/run`
    with `:shared` only under Docker, plus `run_default_volumes_<engine>` (`roles/common/defaults/main.yml:22, :103`;
    `group_vars/all.yml:174-181`).
- **What restarts, changed in 2025.1:** only the containers that differ [CODE]. `check-containers.yml` imports
  `service-check-containers` (`roles/common/tasks/check-containers.yml:2-3`), whose looped `compare_container`
  carries no `notify` and whose next task notifies `Restart <name> container` for the changed items only
  (`roles/service-check-containers/tasks/main.yml:4-41`; [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)).
  The config tasks notify nothing. `compare_container` runs `kolla_set_configs --check` in the container, which now
  also compares the `command` ([Kolla images §3.1](../concepts/kolla-images.md#31-what-is-compared)).
  - **First 2025.1 run after 2024.1:** every common container is reported as changed by its unit file
    ([F16](../reference/findings.md#f16)), and is recreated with Docker on Debian or Ubuntu for the new default
    `nofile` ulimit. fluentd also differs by its `config.json` (new source file name) [CODE].
  - A `permissions`-only change of `config.json` is still not seen by the check ([Kolla images
    §3.2](../concepts/kolla-images.md#32-what-is-still-not-compared)).
- **Impact:**
  - fluentd: log shipping gap. The Elasticsearch and OpenSearch outputs buffer to files under `/var/lib/fluentd/data`,
    the `fluentd_data` volume, which a restart or a recreate keeps (`roles/common/defaults/main.yml:115`;
    `roles/common/templates/conf/output/01-es.conf.j2:34-39`, `03-opensearch.conf.j2:34-39`). The tail read positions
    are in `/var/run/fluentd/`, on no volume (`roles/common/templates/conf/input/00-global.conf.j2:13`): [NOT AVAILABLE]
    whether they survive a config-only restart and whether they are lost when the container is recreated (e.g. an
    image or volume change) ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)).
  - cron: log rotation is delayed.
  - kolla_toolbox: no service template references it (only `roles/common/templates/kolla-toolbox.json.j2` names it
    under `roles/*/templates`); Kolla's own tasks use it through the `kolla_toolbox` module, which fails when the
    container is not running (`library/kolla_toolbox.py:113-122`) [CODE]. Its command exits 0 on TERM or QUIT (kolla
    `docker/kolla-toolbox/kolla_toolbox.sh:3-16`).
  - **VM and API impact:** [NOT AVAILABLE]. None of the three is a container that [Tags
    §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running
    VMs [CODE].
- **Hidden coupling:** enabling a service that appears in either list (most OpenStack services, e.g. barbican) changes
  `fluentd.conf` and/or `logrotate.conf` on *every* host ([Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard)). In 2025.1 [CODE]:
  - `enable_valkey` changes both files on every common host (`roles/common/tasks/config.yml:136-137`, `:225`). With
    Octavia and the amphora driver, the jobboard is on by default (`group_vars/all.yml:950`) and the Octavia precheck
    requires Redis or Valkey (`roles/octavia/tasks/precheck.yml:68-71`), so enabling Octavia can bring this change
    along; `enable_redis` changes `logrotate.conf` only (`roles/common/tasks/config.yml:221`);
  - `enable_letsencrypt` adds an input to `fluentd.conf` on every fluentd host (`config.yml:130-131`); its logrotate
    template is not in the logrotate list (`roles/common/tasks/config.yml:178-228`), so `logrotate.conf` does not change;
  - `enable_ovn` changes `fluentd.conf` only on the hosts of the OVN groups
    (`roles/common/templates/conf/input/10-openvswitch.conf.j2:31-85`).

  The changed common containers restart on every common host whose files changed at the next run that includes the
  common play: any run without tags, or a run with `-t common`. A tagged run such as `-t nova` does not trigger it
  ([Reconfigure Nova §3](reconfigure-nova.md#3-what-changes-per-type-of-change-code)).

## 4. Sequence, risks and verification

- **Sequence on each reached host**, from `roles/common/tasks/deploy.yml:2-9` (`reconfigure.yml` imports it,
  `roles/common/tasks/reconfigure.yml:2`):
  1. config (`roles/common/tasks/config.yml:2-289`): config directories; CA certificates if
     `kolla_copy_ca_into_containers`; on EL10, `/var/log/journal`; with Podman, the tmpfiles config; `kolla.target`;
     `config.json` ×3; custom fluentd files (found once, on the deploy host, `run_once` + `delegate_to: localhost`);
     `fluentd.conf`; cron `logrotate.conf`; RabbitMQ Erlang cookie, `rabbitmq-env.conf` and `erl_inetrc` for
     kolla_toolbox. None of these tasks notifies a handler; a change is found by the next step, since the files are
     listed in the containers' `config.json` (e.g. `roles/common/templates/kolla-toolbox.json.j2:4-21`);
  2. check-containers: `service-check-containers`, one `compare_container` per enabled container, then one task that
     notifies the handlers of the changed ones;
  3. bootstrap: `kolla_logs` volume and the `/var/log/kolla` link to `container_engine_volumes_path`
     (`roles/common/tasks/bootstrap.yml:1-16`; `group_vars/all.yml:165-167`);
  4. flush handlers, in definition order: Restart fluentd → Restart kolla-toolbox (→ toolbox `ansible --version`
     init, with `kolla_container_engine exec`) → Restart cron (`roles/common/handlers/main.yml:2`, `:16`, `:33-36`,
     `:38`).
- **`genconfig`** (`kolla_action=config`, `kolla_ansible/cli/commands.py:113-126`) runs `config.yml` only
  (`roles/common/tasks/main.yml:2`): no check, so no restart, and no image pull in 2025.1 [CODE]. The handlers lost
  their `kolla_action != "config"` guard, which no longer matters because nothing notifies them in that action.
- **Hosts, parallelism:** all reached hosts at once, unless batched with `--limit` or `deploy -e kolla_serial=N`
  ([§1.1](#11-apply-common-changes-fluentd-cron-kolla_toolbox)).
- **Interruption:** one stop/start per changed container. With Docker, a restart goes through the container's systemd
  unit and a recreate stops it through the unit when one exists; the unit's `ExecStop` is `<engine> stop <name> -t
  <graceful_timeout>`, with `docker_graceful_timeout: 60` (`module_utils/kolla_docker_worker.py:426-442`, `:450-470`; `module_utils/kolla_systemd_worker.py:33`; `group_vars/all.yml:148,160`; [Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). A recreate
  pulls the image first when it is absent (`module_utils/kolla_docker_worker.py:352-374`). Log shipping pauses, cron
  rotation is delayed, and Kolla's own `kolla_toolbox` tasks fail while the container is not running. [NOT AVAILABLE]
  Whether VMs, APIs, networking or storage are affected ([§3](#3-how-common-actually-reaches-hosts)).
- **Risks:** [R2](../risk/risk-register.md#r2) (fleet-wide restarts after an `enable_*` change),
  [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a reconfigure; in 2025.1 `-t common` does reconfigure,
  see [§2](#2-the-tag-does-nothing)), [F16](../reference/findings.md#f16) (first 2025.1 check after 2024.1).
- **Verification:**
  - before: `genconfig`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check; echo $?` in each of
    `fluentd`, `cron` and `kolla_toolbox` (`podman exec` with Podman). 1 in one of them = that container will restart;
    a `logrotate.conf`-only change, e.g. toggling `enable_redis`, shows up only in `cron`. The check covers the files
    and, new in 2025.1, the command; it does not cover image, volume or unit-file changes, which `compare_container`
    compares itself. `kolla-ansible check -t common` (new in 2025.1) reports common containers that are missing,
    stopped or unhealthy, not pending changes;
  - after: `docker ps --filter name=fluentd --filter name=cron --filter name=kolla_toolbox` shows fresh start times
    for the changed containers; `docker logs fluentd` has no parse errors; logs still reach the configured output.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R2](../risk/risk-register.md#r2) (fleet-wide
  restarts after an `enable_*` change) and [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a
  reconfigure)
- [Common: fluentd, cron, kolla_toolbox](../components/common.md) — service card and where to look
- [Chrony](../components/chrony.md) — the Ussuri tag used to push `common` changes; the role does not exist in 2025.1
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Controlled batches](controlled-batches.md) — `genconfig` first, then batches; `kolla_serial` and `--limit`
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — dynamic `include_tasks` and tag
  inheritance: the tag semantics behind §2
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common` role and the `common_run` guard (gone since 2023.1)
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) —
  `enable_<new service>: yes` changes fluentd/logrotate on every host
