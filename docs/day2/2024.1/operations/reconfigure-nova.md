---
title: Reconfigure Nova
description: "What -t nova reconfigure runs in 2024.1 on controllers and every compute, which changes restart nova_compute, nova_libvirt, nova_ssh, risks, checks."
tags: [nova, libvirt, reconfigure, genconfig, loop-notify, serial, one-shot, kolla-set-configs, max-fail-percentage]
impact: [restarts-on-drift]
---

# Reconfigure Nova

What `kolla-ansible -t nova reconfigure` does on the loadbalancer hosts, on the controllers and on every compute, with
the
two narrower commands `-t nova-api reconfigure` (only the Nova control plane, no compute impact) and
`-t nova-cell reconfigure` (only the cell part: conductors, consoles, computes).

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
[conventions of the command sections](index.md#conventions-used-by-the-command-sections), the definition of
[drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!NOTE]
> **Key answers**
>
> - **`-t nova reconfigure` ([§2 to §6](#2-execution-sequence-kolla-ansible--t-nova-reconfigure)):** every compute runs
>   the tasks. Restarts happen only where drift is detected, in practice on no compute or on all of them, and
>   `nova_libvirt` and `nova_ssh` restart whenever `nova_compute` restarts because of config or image drift
>   ([§4](#4-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute)). Whether running VMs survive is
>   [NOT AVAILABLE] ([§5](#5-running-vms-live-migration-scheduling)).
> - **First 2024.1 run after 2023.1:** expect drift on every Nova container, computes included: the systemd unit text
>   changed ([F16](../reference/findings.md#f16)), quorum queues are on by default ([F17](../reference/findings.md#f17))
>   and `nova_compute` has a new `hostnqn` file ([§3](#3-what-changes-per-type-of-change-code)).
> - **Nova without touching computes:** `-t nova-api reconfigure`
>   ([§1.2](#12-reconfigure-only-the-nova-control-plane-no-compute-impact)).

> [!WARNING]
> [R1](../risk/risk-register.md#r1): a nova-compute drift restarts `nova_compute`, `nova_libvirt` and `nova_ssh` on
> each compute where it occurs, so a change common to all computes restarts them on every compute — see
> [§4](#4-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute).

## 1. Commands

### 1.1 Reconfigure Nova (control plane and computes)

```bash
kolla-ansible -i multinode -t nova reconfigure
```

- **Scope:**
  - loadbalancer play (nova and nova-cell frontends; `site.yml:252-265`, inside a block that runs for `deploy`,
    `reconfigure`, `upgrade` and `config` when `enable_haproxy` is set, `site.yml:324-326`);
  - the 10 nova plays (`nova.yml:29-302`), the nova-cell play on **every compute** (`nova.yml:125-147`);
  - `common` does not run under `-t nova`: it is its own play, tagged `common` only (`site.yml:88-103`).
- **One-shot:** 6 container runs on `control01` (API DB sync, `map_cell0`, `list_cells` for cell0, cell DB sync,
  `list_cells` ×2) plus RabbitMQ user/vhost, Keystone registration, SIGHUP of `nova_scheduler`, `discover_hosts`
  [CODE, when cell0 is mapped with an unchanged connection and the cell is unchanged:
  `roles/nova/tasks/bootstrap.yml:54-56`, `roles/nova/tasks/map_cell0.yml:2-30`,
  `roles/nova-cell/tasks/bootstrap.yml:37-43`, `roles/nova-cell/tasks/create_cells.yml:2-4`,
  `roles/nova-cell/tasks/discover_computes.yml:4-18`, `roles/nova/tasks/deploy.yml:2`; [Tags
  §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)].
- **Restarts:** depend on the drift ([§2 to §6](#2-execution-sequence-kolla-ansible--t-nova-reconfigure)). A
  nova-compute drift restarts `nova_compute`, `nova_libvirt` and `nova_ssh` on each compute where it occurs, so a change
  common to all computes restarts them on every compute [CODE `roles/nova-cell/tasks/check-containers.yml:2-22`,
  loop-notify, [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)].
- **Failures:** new in 2024.1, seven of the ten plays set `max_fail_percentage` (default 100, which never stops a play
  early); the cell DB bootstrap play and the two online-data-migration plays set `any_errors_fatal: true` instead
  (`nova.yml:40-43`, `nova.yml:79`, `nova.yml:141-144`, `nova.yml:269-270`, `nova.yml:294-295`) [CODE].

### 1.2 Reconfigure only the Nova control plane (no compute impact)

```bash
kolla-ansible -i multinode -t nova-api reconfigure
```

- **Scope:** the `nova-api`-tagged plays (API DB bootstrap, nova role, scheduler refresh, and the API reload and
  online-migration plays, which do nothing outside `upgrade`) on controllers (`nova.yml:29-65`, `nova.yml:103-122`,
  `nova.yml:152-172`, `nova.yml:180-201`, `nova.yml:231-277`), plus the loadbalancer nova include (`site.yml:252-258`).
- **Not touched:** conductors and computes (`nova-cell` plays, `nova.yml:67-100`, `nova.yml:124-147`).

### 1.3 Reconfigure only the cell part (conductors, consoles, computes)

```bash
kolla-ansible -i multinode -t nova-cell reconfigure
```

- **Scope:** the `nova-cell`-tagged plays (cell DB bootstrap, nova-cell role, and the cell reload and online-migration
  plays, which do nothing outside `upgrade`) (`nova.yml:67-100`, `nova.yml:124-147`, `nova.yml:203-229`,
  `nova.yml:283-302`), plus the loadbalancer nova-cell include for the console proxies (`site.yml:259-265`). The
  nova-cell
  play reaches every compute, as with `-t nova`.

## 2. Execution sequence (`kolla-ansible -t nova reconfigure`)

```mermaid
sequenceDiagram
  autonumber
  participant HA as loadbalancer hosts
  participant C1 as control01 (nova-api[0], conductor[0])
  participant CT as all controllers
  participant CP as all computes
  Note over HA: loadbalancer play — nova + nova-cell includes only
  HA->>HA: render services.d/nova*.cfg, restart haproxy only if changed
  Note over CT: Play 1 Bootstrap API DBs
  C1->>C1: mysql_db/mysql_user (toolbox) · nova_api_bootstrap (db sync) · map_cell0 · list_cells (cell0)
  Note over CT: Play 2 Bootstrap cell DBs (any_errors_fatal)
  C1->>C1: cell DB/user · RabbitMQ vhost/user · nova_cell_bootstrap (cell db sync) · list_cells → update_cell if URLs changed
  Note over CT: Play 3 nova role — register (keystone) · config · check · flush
  CT->>CT: restart super-conductor/scheduler/api if drift (all controllers at once)
  Note over CT,CP: Play 4 nova-cell — config-host · config · check · flush
  CT->>CT: restart conductor/novncproxy if drift (all controllers at once)
  CP->>CP: restart nova_ssh → nova_libvirt (→ SASL user) → nova_compute if drift (all computes at once)
  CP->>C1: wait for compute registration · list_cells · discover_hosts (delegated)
  Note over CT: Play 5 — kill -HUP nova_scheduler (always)
  Note over CT,CP: Plays 6-10 — skipped (upgrade only)
```

Read from the 2024.1 code [CODE]: the loadbalancer includes render the frontends and notify the HAProxy restart
(`roles/nova/tasks/loadbalancer.yml:2-7`, `roles/haproxy-config/tasks/main.yml:2-23`); play 1
(`nova.yml:29-65`; `roles/nova/tasks/bootstrap.yml:2-56`, `roles/nova/tasks/map_cell0.yml:2-67`); play 2
(`nova.yml:67-100`; `roles/nova-cell/tasks/bootstrap.yml:2-43`, `roles/nova-cell/tasks/create_cells.yml:2-55`);
play 3 (`nova.yml:103-122`; `roles/nova/tasks/deploy.yml:1-9`); play 4 (`nova.yml:125-147`;
`roles/nova-cell/tasks/deploy.yml:1-39`, `roles/nova-cell/tasks/wait_discover_computes.yml:7-90`,
`roles/nova-cell/tasks/discover_computes.yml:4-23`); play 5 (`nova.yml:152-172`;
`roles/nova/tasks/refresh_scheduler_cell_cache.yml:4-12`); plays 6 to 10 run their tasks only when `kolla_action` is
`upgrade` (`nova.yml:199-201`, `:227-229`, `:251-253`, `:275-277`, `:300-302`). With the default `kolla_serial` 0, each
play takes all its hosts in one batch (e.g. `nova.yml:140`).

## 3. What changes, per type of change [CODE]

| Change | Files rewritten | Restarted on controllers | Restarted on **every compute** | Source |
|---|---|---|---|---|
| none | – | none unless a notifying task reports changed | none unless a notifying task reports changed | restart handlers run only when a notifying task reports changed ([Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)), and `check-containers` reports changed only for a missing container, a differing compared parameter, a `kolla_set_configs --check` exit 1/137 or Docker client error, or a missing or different systemd unit file `kolla-<container>-container.service` (`module_utils/kolla_container_worker.py:58-89`, `module_utils/kolla_docker_worker.py:146-181`, `module_utils/kolla_systemd_worker.py:154-167`; [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)); [NOT AVAILABLE] whether every task reports unchanged on an unchanged cloud |
| first 2024.1 run after 2023.1, no operator change (new in 2024.1) | `nova.conf` of every nova service when quorum queues were off in 2023.1; `nova-compute/hostnqn` and `nova-compute/config.json`; `nova-ssh/sshd_config` on Debian and Ubuntu images | every nova container whose systemd unit 2023.1 wrote; every one whose `nova.conf` changed | **nova_compute, nova_libvirt, nova_ssh** | unit text: [F16](../reference/findings.md#f16) (`module_utils/kolla_systemd_worker.py:20-39`, `:154-167`); quorum default: [F17](../reference/findings.md#f17) (`group_vars/all.yml:268`, `roles/nova/templates/nova.conf.j2:156-165`, `roles/nova-cell/templates/nova.conf.j2:207-216`); `hostnqn`: `roles/nova-cell/tasks/config.yml:203-216`, `roles/nova-cell/templates/nova-compute.json.j2:59-64`, config.json loop `roles/nova-cell/tasks/config.yml:56-67`; `sftp` line: `roles/nova-cell/templates/sshd_config.j2:9-13`, `roles/nova-cell/tasks/config.yml:162-167`. When the run is the `upgrade`, it renders the same configs and checks the same containers (`roles/nova-cell/tasks/rolling_upgrade.yml:1-18`) |
| `/etc/kolla/config/nova.conf` (global override) | `nova.conf` of every nova service | nova_api, nova_scheduler, nova_conductor, nova_novncproxy | **nova_compute, nova_libvirt, nova_ssh** | both `Copying over nova.conf` loops merge `{{ node_custom_config }}/nova.conf` (`roles/nova/tasks/config.yml:64-82`, `roles/nova-cell/tasks/config.yml:69-89`); [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| `/etc/kolla/config/nova/nova-compute.conf` | `nova-compute/nova.conf` only | – | **nova_compute, nova_libvirt, nova_ssh** (libvirt and ssh by loop-notify) | `roles/nova-cell/tasks/config.yml:69-89`, source at `:78`; [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| `/etc/kolla/config/nova/<host>/nova-compute.conf` (new source in 2024.1) | `nova-compute/nova.conf` of that host only | – | **nova_compute, nova_libvirt, nova_ssh** on that compute only | `roles/nova-cell/tasks/config.yml:80`; the nova role has no such per-service host source (`roles/nova/tasks/config.yml:69-74`) |
| `/etc/kolla/config/nova/nova-scheduler.conf` | `nova-scheduler/nova.conf` only | nova_scheduler **+ nova_api** (loop-notify) | – | `roles/nova/tasks/config.yml:64-82`; [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| `enable_barbican: yes` (Barbican not even deployed) | `nova.conf` everywhere (adds `[barbican]`). `td-agent.conf` and `logrotate.conf` change too, but only when the `common` play runs (no tag or `-t common`), not under `-t nova` | all nova (fluentd and cron only at the next `common` run) | all nova incl. libvirt (same for fluentd and cron) | `roles/nova/templates/nova.conf.j2:217-222`, `roles/nova-cell/templates/nova.conf.j2:259-264`; `roles/common/defaults/main.yml:154-158`, `roles/common/tasks/config.yml:140-203`, `roles/common/tasks/config.yml:205-270`; `site.yml:88-103`; [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| same as the global `nova.conf` override, with `kolla_serial=1` | same | one controller at a time | **one compute at a time**; API DB sync and `map_cell0` repeated per batch (3×) | `nova.yml:39, :115, :140`; `roles/nova/tasks/bootstrap_service.yml:2-21`, `roles/nova/tasks/map_cell0.yml:63-64`; [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code) |

## 4. Are all compute nodes affected? Does nova-compute restart on every compute?

- **Tasks:** yes. The nova-cell play targets the whole `compute` group (`nova.yml:125-147`). Read from the 2024.1 task
  files, a no-change run makes 27 remote module invocations per compute and 31 on the first compute (for the default
  service set with Cinder LVM, `kvm`, Docker and a non-Ubuntu host); 2023.1 made 26 and 30, and the new invocation is
  the `hostnqn` template (`roles/nova-cell/tasks/config.yml:203-216`; [Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)). Its number of
  task results is [NOT AVAILABLE].
- **Restarts:** only where drift is detected. But most Nova-related changes are global ([Component dependencies
  §5](../components/dependencies.md#5-compute-node-dependency-summary), [Nova deep dive
  §2.3](../components/nova-deep-dive.md#23-configuration-dependencies-inputs-that-change-novas-files)), so in practice
  either *no* compute restarts or *all* computes restart. They restart in the same handler step unless
  `ANSIBLE_SERIAL`/`kolla_serial` is set or `--limit` is used (`nova.yml:140`; `tools/kolla-ansible:531`).
- **libvirt goes with it.** Whenever nova-compute restarts because of config or image drift, **nova-libvirt and nova-ssh
  restart too** (loop-notify, [Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). Kolla's own handler
  ordering restarts nova-ssh, then libvirt, *before* nova-compute [CODE] (`roles/nova-cell/handlers/main.yml:74-168`;
  handlers run in definition order: the iterator copies the play's handler list in order and, during a flush, walks it
  and runs each notified one, ansible-core 2.16.20 `lib/ansible/executor/play_iterator.py:195-200`,
  `lib/ansible/executor/play_iterator.py:426-445`). With `libvirt_enable_sasl` (default `true`,
  `roles/nova-cell/defaults/main.yml:569`), the libvirt handler also notifies a readiness check and the SASL user
  creation, defined before the nova-compute handler (`roles/nova-cell/handlers/main.yml:96`,
  `roles/nova-cell/handlers/main.yml:116-141`).

## 5. Running VMs, live migration, scheduling

| Effect | Guaranteed by code | Depends on environment |
|---|---|---|
| nova-compute stop/start (stop with `docker_graceful_timeout`, 60 s by default, `group_vars/all.yml:139`) | yes, when drift | [NOT AVAILABLE] Whether VMs are unaffected, whether in-flight operations on that host fail or are left mid-task, and whether the service is reported down only if the restart exceeds `service_down_time` ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)) |
| libvirtd stop/start | yes, whenever nova-compute drifts | [NOT AVAILABLE] Whether VMs survive. [CODE] The container has `pid_mode: host`, `cgroupns_mode: host` (now always compared and set by the Docker worker, `module_utils/kolla_container_worker.py:142-155`, `module_utils/kolla_docker_worker.py:300-304`), the host `/run` bind mount and `/sys/fs/cgroup` mounted rw (`roles/nova-cell/defaults/main.yml:8-9`, `:374`, `:377`), and the image's start scripts do nothing to QEMU, cgroups or `/var/run/libvirt` (kolla `docker/base/start.sh:1-24`, `docker/nova/nova-libvirt/extend_start.sh:1-16`; [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)). The open questions are therefore libvirt and container-engine behaviour: where libvirtd puts QEMU (for example a host `machine.slice` scope), the stop (each container is run by a systemd unit `kolla-<name>-container.service` whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`, 60 s by default; a restart of an unchanged container restarts that unit, a recreate stops it, removes the container and starts a new one, and without a unit file the Docker worker calls the engine's `stop` with the same timeout; `module_utils/kolla_systemd_worker.py:20-39`, `:106-125`, `module_utils/kolla_docker_worker.py:341-363`, `:415-431`, `:439-459`, `group_vars/all.yml:139`, `:151`; on a container whose entrypoint is dumb-init, kolla `docker/base/Dockerfile.j2:370`; which signals Docker sends, at the stop and after the timeout, is [NOT AVAILABLE]) and libvirtd re-attaching to running domains when it starts. [NOT AVAILABLE] Whether live migrations in progress fail, and whether libvirt API calls fail until libvirtd is back ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)) |
| nova-ssh stop/start | yes, with the above | [NOT AVAILABLE] Whether resize or cold-migration disk copies over port 8022 (`roles/nova-cell/defaults/main.yml:480`) are interrupted |
| Scheduling | API and scheduler restarts are parallel on all controllers (serial 0, `nova.yml:115`) | [NOT AVAILABLE] Whether API calls fail during the restart window. [CODE] The scheduler gets SIGHUP on every deploy or reconfigure run that reaches its hosts (cell-cache refresh, `nova.yml:152-172`, `roles/nova/tasks/refresh_scheduler_cell_cache.yml:4-12`); [NOT AVAILABLE] whether that is harmless |
| Host mapping | `discover_hosts` runs every time | runs `nova-manage cell_v2 discover_hosts --by-service` to map newly registered computes (`roles/nova-cell/tasks/discover_computes.yml:14-18`, through `kolla_container_engine exec -t nova_conductor`, `-t` new in 2024.1); [NOT AVAILABLE] whether it affects existing instances |

## 6. Operational risks and verification

- **Risks:** [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2), [R3](../risk/risk-register.md#r3),
  [R24](../risk/risk-register.md#r24) in [Risk register](../risk/risk-register.md); after an upgrade from 2023.1,
  [F16](../reference/findings.md#f16) and [F17](../reference/findings.md#f17).
- **Before:**
  - `kolla-ansible -t nova genconfig` (restarts nothing: `kolla_action` is `config`, `tools/kolla-ansible:557-559`, and
    every Nova restart handler is skipped then, `roles/nova/handlers/main.yml:16-17`,
    `roles/nova-cell/handlers/main.yml:167-168`), then diff `/etc/kolla/nova-*/nova.conf` on one controller and one
    compute.
  - `docker exec -u root nova_compute /usr/local/bin/kolla_set_configs --check; echo $?` on a few computes (with
    `kolla_container_engine: podman`, `podman exec`): exit 1 means the container *will* restart, and so will
    `nova_libvirt` and `nova_ssh` ([Kolla images
    §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)). The check does
    not see the unit-file drift of [F16](../reference/findings.md#f16), which the module compares on the host
    (`module_utils/kolla_container_worker.py:58-65`).
  - No active live migrations: `openstack server list --all-projects --status MIGRATING`.
- **Apply in batches:** `deploy-containers --limit` ([Write config first, apply in controlled batches
  §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)) or `ANSIBLE_SERIAL`; to stop a
  rolling run when a batch has failures, set `nova_cell_max_fail_percentage` (cell plays) or `kolla_max_fail_percentage`
  lower than the default 100 (`nova.yml:141-144`; [Write config first, apply in controlled batches
  §1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
- **After:**
  - `openstack compute service list` (all up);
  - `docker ps --filter name=nova_ -a` (all `Up`, recent `Created`/`Started`);
  - `virsh list --all` inside `nova_libvirt` on a sample of computes (domains running), with guest pings;
  - `nova-manage cell_v2 list_hosts` count equals the number of computes.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R1](../risk/risk-register.md#r1) (any config
  change touching nova-compute), [R2](../risk/risk-register.md#r2) (fleet-wide restarts after an `enable_*` change),
  [R3](../risk/risk-register.md#r3) (changing RabbitMQ group membership, password or port) and
  [R24](../risk/risk-register.md#r24) (container stop timeout: `docker_graceful_timeout`, 60 s by default)
- [Technical findings](../reference/findings.md) — [F16](../reference/findings.md#f16) (the changed systemd unit
  template) and [F17](../reference/findings.md#f17) (quorum queues by default), both new in 2024.1
- [Nova](../components/nova.md) — service cards of the roles `nova` and `nova-cell`, what changed in 2024.1, and where
  to look
- [Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special) — nova-libvirt: why
  its restart is special
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Write config first, apply in controlled batches](controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch, rolling runs with `ANSIBLE_SERIAL`, and `max_fail_percentage`
- [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify:
  one changed item notifies the handlers of all items
- [Compute scaling
  §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files) — work per
  compute host, read from the task files: the source of the per-compute counts of §4
