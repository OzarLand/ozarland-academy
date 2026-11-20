---
title: Compute scaling and performance
description: Which Kolla-Ansible Ussuri operations grow with the number of compute nodes, why, and how to bound them.
tags: [scaling, nova, limit, serial, facts, loop-notify, pull, images]
remember:
  - "With the default linear strategy, the next task starts only when every host has finished the current one: the slowest host sets the pace. <span class=\"ev ev-code\">CODE</span>"
  - "Adding computes adds waves, not tasks: a task on H hosts needs ⌈H/F⌉ waves, F being <code>forks</code>."
  - "<code>--limit</code> bounds the restarts, but fact gathering stays O(inventory). <span class=\"ev ev-code\">CODE</span>"
  - "Every run that includes the <code>compute</code> group executes the full per-host chain on every compute, even with no change."
  - "<code>serial</code> bounds simultaneous restarts per play, but adds time."
quiz:
  - q: "Does this study give how long a run takes?"
    options: ["Yes, measured on a lab", "No: work is counted as operations read from the source"]
    answer: 1
    explain: "Task-result totals and wall times are NOT AVAILABLE: nothing was run against a host."
    see: "2-work-per-compute-host-read-from-the-task-files"
  - q: "What do more computes add to a play?"
    options: ["More tasks on each host", "More waves: ⌈H/F⌉, with H hosts and F forks"]
    answer: 1
    explain: "The critical path of a play is the number of executed task-items on the slowest host × ⌈H/F⌉ waves."
    see: "41-model"
  - q: "Does <code>--limit</code> reduce fact gathering?"
    options: ["Yes, facts are gathered only on the limited hosts", "No: <code>--limit</code> bounds the restarts, but fact gathering stays O(inventory)"]
    answer: 1
    explain: "Read from the code <span class=\"ev ev-code\">CODE</span>."
    see: "6-scaling-at-3-10-and-30-computes-read-from-the-code"
---

# Compute scaling and performance

Which Kolla-Ansible Ussuri operations grow with the number of compute nodes, why, and how to bound them.

> [!NOTE]
> **Key answers**
>
> - **No timings are given.** Work is counted as operations read from the source; task-result totals and wall times are
>   [NOT AVAILABLE] ([§2](#2-work-per-compute-host-read-from-the-task-files), [§4.1](#41-model)).
> - **Per compute, for the default Ussuri service set with Cinder LVM, `nova_compute_virt_type: kvm` and a CentOS host,
>   a no-change `-t nova reconfigure` makes 46 remote module invocations (53 on compute001) and 6 `compare_container`
>   calls; a full `deploy` or `reconfigure` makes 11 `compare_container` calls** [CODE]
>   ([§2](#2-work-per-compute-host-read-from-the-task-files)).
> - **Adding computes adds waves, not tasks:** the critical path of a play is the number of executed task-items on the
>   slowest host × ⌈H/F⌉ waves ([§4.1](#41-model)). Operation counts for 10 to 500 computes:
>   [§4.2](#42-operation-counts-by-fleet-size).
> - **`--limit` bounds the restarts, but fact gathering stays O(inventory)** [CODE]
>   ([§6](#6-scaling-at-3-10-and-30-computes-read-from-the-code)).
> - **Why a small change becomes a large workload:** a work multiplier (every run that includes the `compute` group
>   executes the full per-host chain on every compute, even with no change) and a restart multiplier (global inputs,
>   loop-notify, no `serial`) ([§5](#5-why-a-small-change-becomes-a-large-workload)).
> - **What to do about it:** the ranked optimisations ([§8](#8-bottlenecks-and-optimisation-opportunities-ranked)).
>   `serial` bounds simultaneous restarts per play, but adds time ([§7](#7-influence-of-the-main-variables)).

> **No timings are given here.** Work is expressed as *operation counts* read from the source and as formulas whose
> parameters depend on your own environment. Nothing was run against a host. The evidence labels **[CODE]** and
> **[NOT AVAILABLE]** are defined once, in [Evidence labels](../start/conventions.md#evidence-labels). Here
> [NOT AVAILABLE] covers, for example, task-result totals and wall times.

---

## 1. How Ansible 2.9 spends time in Kolla-Ansible

| Factor | Mechanism | Consequence for Kolla |
|---|---|---|
| **Linear strategy (default)** | A task runs on **all hosts of the play** (up to `forks` at a time), and the **next task starts only when every host has finished the current one** [CODE: ansible 2.9.27 `lib/ansible/plugins/strategy/linear.py:311, :324-326`] | The slowest host sets the pace of every task. One slow compute (disk, SSH, Docker) slows the whole fleet |
| **forks** (Ansible default 5; Kolla docs suggest 20–100) | Max parallel host executions per task: one worker process per fork, at most the batch size [CODE: ansible 2.9.27 `lib/ansible/executor/task_queue_manager.py:82, :257-258`] | A task on *H* hosts needs ⌈H/F⌉ waves |
| **Loops** (`with_dict: <role>_services`, `with_items`) | Items run **sequentially on each host** [CODE: ansible 2.9.27 `lib/ansible/executor/task_executor.py:317, :367`]; each item that passes its `when` is a separate module execution (separate remote command); skipped items run no module | `config.yml` and `check-containers.yml` cost *items × invocation latency* per host |
| **Remote module invocation** | Without pipelining, each invocation = SSH exec to create a tmp dir, transfer the AnsiballZ payload, run it, clean up. With `become`, `sudo` is added | The fixed cost per invocation dominates idempotent runs |
| **Deploy-host templating** | `template` and `merge_configs` render **on the deploy host** for every host and item, then `copy` compares checksums remotely [CODE: `ansible/action_plugins/merge_configs.py:151-161, :214`; ansible 2.9.27 `lib/ansible/plugins/action/template.py:149, :182-189`, `lib/ansible/plugins/action/copy.py:266, :288`] | Deploy-host CPU scales with hosts × templates. `nova.conf.j2` and `neutron.conf.j2` are large, with loops over groups |
| **Controller-side tasks** | `group_by`, `set_fact`, `include_*`, `meta` run in Ansible workers without SSH | Cheap per host, but not free: the 69-item `group_by` loop (`site.yml:21-95`) is templated in a deploy-host worker for every host, and `group_by` runs no module on the host [CODE: ansible 2.9.27 `lib/ansible/plugins/action/group_by.py:31-51`]. Its CPU cost per host is [NOT AVAILABLE] |
| **`run_once` / `delegate_to`** | Run once (per batch) on one host | Constant cost unless `serial` multiplies it |
| **Handlers** | Run at flush points on notified hosts, in parallel up to `forks` [CODE: ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:1019-1035`] | Restart time of the slowest container on the slowest host |
| **`until`/`retries` loops** | e.g. compute registration wait (20 × 10 s), Keystone registration retries (5 × 10 s), `wait_for` | Add up to retries × delay of sleep per task, plus the time of each attempt [CODE: ansible 2.9.27 `lib/ansible/executor/task_executor.py:642-648, :758-763`]; how many attempts a run needs is [NOT AVAILABLE] |
| **Fact gathering** | `setup` on every host at the start (`gather-facts.yml:5-21`). With `--limit`, the limited hosts gather **all other hosts' facts sequentially** in a delegated loop (`gather-facts.yml:29-50`) | O(total hosts) serial latency per limited run without fact caching |

---

## 2. Work per compute host (read from the task files)

Counts below are read from the task files of the roles that run on a compute [CODE], for the default Ussuri service
set with Cinder LVM (which adds `iscsid` on computes: `group_vars/all.yml:601, :651`,
`roles/iscsi/defaults/main.yml:67-72`), `nova_compute_virt_type: kvm` (`group_vars/all.yml:966`) and a CentOS host
(Ubuntu adds one `systemd` call: `roles/nova-cell/tasks/config-host.yml:48-56`). Task-result totals depend on how
skipped tasks, includes and `meta` tasks are counted at run time; the sources do not give them [NOT AVAILABLE].

- A "task result" is one task × one host, including skipped tasks.
- A "remote invocation" is one module execution on the host, counting each executed loop item. Loop items skipped by
  `when` run no module and are not counted (for example, on a compute at least 5 of the 8 items of each
  `nova_cell_services` loop are skipped: `roles/nova-cell/defaults/main.yml:2-64`).
- Controller-only work is excluded from the invocation count: `group_by`, `set_fact`, `include_*`.
- Each `template`, `copy` or `merge_configs` item counts as one invocation, although the copy action behind them runs
  two modules on the host when the file is unchanged (remote `stat`, then `file`) [CODE: ansible 2.9.27
  `lib/ansible/plugins/action/copy.py:266, :288, :383`]. SSH round trips are therefore higher than the invocation
  count.
- Where two figures are given, the higher one is compute001, the first host of the nova-cell play (`nova.yml:117-120`).
  It also runs the delegated `run_once` steps: compute discovery on the first conductor, control01 (3 invocations:
  `roles/nova-cell/tasks/wait_discover_computes.yml:8-42`, `get_cell_settings.yml:2-20`,
  `discover_computes.yml:14-21`) and, in `-t nova` runs, four `find` calls on the deploy host
  (`roles/common/tasks/config.yml:73-107`).
- *N* is the number of inventory hosts in `groups['all']`, localhost included (`inventory/multinode:32-33`).

| Action | Task results per compute | Executed (non-skipped) | Remote module invocations per compute | `compare_container` calls per compute (one `docker exec kolla_set_configs --check` each when the container exists) | Source |
|---|---|---|---|---|---|
| `deploy` (first time) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 11 calls, 0 execs (containers missing) | `check-containers.yml` of common (3), chrony, iscsi, openvswitch (2), neutron, nova-cell (3); `library/kolla_docker.py:326-332` |
| `deploy` (no change) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 11 | as above |
| `reconfigure` (no tag, no change) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 11 | as above |
| `-t nova reconfigure` (no change) | NOT AVAILABLE | NOT AVAILABLE | 46 (53 on compute001) | 6 (3 common + 3 nova) | breakdown below |
| `-t nova reconfigure --limit compute001` (no change) | NOT AVAILABLE | NOT AVAILABLE | 53 + delegated fact loop (*N* − 1) | 6 | breakdown below; `gather-facts.yml:29-50` |
| `-t nova deploy-containers --limit compute001` (no change) | NOT AVAILABLE | NOT AVAILABLE | 7 (`setup` + 6 `compare_container`) + delegated fact loop (*N* − 1) | 6 | `roles/common/tasks/deploy-containers.yml:2`, `roles/nova-cell/tasks/deploy-containers.yml:2` |
| `pull` (all) | NOT AVAILABLE | NOT AVAILABLE | 13 (`setup`, CentOS `slurp`, 11 image pulls) | 0 | `site.yml:97-105`; `roles/service-images-pull/tasks/main.yml:2-14` |
| `-t haproxy reconfigure` | 5 (facts + group_by only) | 5 | 1 (`setup`) | 0 | `docs/day2/ussuri/reference/listings/list-tasks-nova.txt:106-119` (plays tagged `always`); `site.yml:126-136` (the only play tagged `haproxy` targets the `haproxy` group) |

Breakdown of the 46 remote invocations of a no-change `-t nova` run on one compute, read from the task files [CODE]
(compute001 adds 7 delegated invocations, for 53):

| Kind | Invocations | Source |
|---|---|---|
| `template` items (config.json ×3 common, td-agent, logrotate, module-load persistence, udev rule, config.json nova-cell ×3, libvirt ×2, SASL ×3, ssh files ×4) | 19 | common, module-load, nova-cell `config-host.yml` + `config.yml` (`roles/common/tasks/config.yml:62-71, :109-161, :163-240`; `roles/module-load/tasks/main.yml:23-33`; `roles/nova-cell/tasks/config-host.yml:35-43`; `roles/nova-cell/tasks/config.yml:43-54, :84-99, :107-125, :127-144`) |
| `file` items (config dirs ×3 common and ×3 nova-cell, ownership ×2, kolla_logs link) | 9 | common + nova-cell (`roles/common/tasks/config.yml:2-24, :252-263`; `roles/common/tasks/bootstrap.yml:9-14`; `roles/nova-cell/tasks/config.yml:2-13`) |
| `kolla_docker` (compare_container ×6, ensure_image, create_volume) | 8 | check-containers, common (`roles/common/tasks/check-containers.yml:2-17`; `roles/nova-cell/tasks/check-containers.yml:2-20`; `roles/common/tasks/config.yml:26-37`; `roles/common/tasks/bootstrap.yml:2-7`) |
| `merge_configs` (nova.conf ×1 on a compute) | 1 | nova-cell `config.yml` (`roles/nova-cell/tasks/config.yml:63-82`; `roles/nova-cell/defaults/main.yml:349-355`) |
| `sysctl` ×4, `modprobe`, `stat`, `copy`, `setup`, `docker_image_info` | 9 | facts, common, module-load, nova-cell `config-host.yml` (`gather-facts.yml:10-15`; `roles/common/tasks/config.yml:39-49, :242-250`; `roles/module-load/tasks/main.yml:8-21`; `roles/nova-cell/tasks/config-host.yml:11-29`) |

Per-**controller** counts are [NOT AVAILABLE]. Controllers carry more roles than computes, but they are few.
Compute-side work is what scales.

### 2.1 Fleet totals scale linearly

Total task results ≈ `fixed + Σ_hosts per-host count`:

- **Full no-change `reconfigure`, 3 computes:** the fleet and per-compute task-result totals are [NOT AVAILABLE].
- **Each additional compute adds** [CODE, counts from [§2](#2-work-per-compute-host-read-from-the-task-files)]:
  - 11 `compare_container` calls (11 `kolla_set_configs --check` execs once its containers exist) to every full
    `deploy`/`reconfigure`; the task results and remote invocations it adds to a full run are [NOT AVAILABLE];
  - 46 remote invocations and 6 checks to every `-t nova` run; the task results it adds are [NOT AVAILABLE].

The same scenarios at 10 and 30 computes, with forks 5/20/50, are in
[§6](#6-scaling-at-3-10-and-30-computes-read-from-the-code).

---

## 3. Expensive tasks and their scaling factors

Scope legend:

- **D** = once per deployment (`run_once`, delegated);
- **Ctl** = once per controller;
- **C** = once per compute;
- **C×S** = once per compute and per container/service;
- **H** = once per host of any kind;
- **Cond** = only when a condition holds (e.g. drift).

| Task | Role / file | Target hosts | Scope | Scaling factor | Why it can be slow | Optimisation |
|---|---|---|---|---|---|---|
| Fact gathering (`setup`) | `gather-facts.yml:5-21` | all | H | ⌈N/F⌉ waves | full `setup` collects hardware, network (many interfaces with OVS/Neutron), mounts; facter/ohai if present | `kolla_ansible_setup_filter: "ansible_[!qt]*"` (skips `qvo`/`tap` interface facts), `kolla_ansible_setup_gather_subset`, fact caching (`gathering = smart` + jsonfile) — documented in `doc/source/user/ansible-tuning.rst` |
| Delegated fact gathering under `--limit` | `gather-facts.yml:29-50` | limited hosts gather everyone | **N sequential per limited host** (N/L each) | O(N) serial | `delegate_to` loop runs items one after another | Fact cache; avoid `--limit` with a single host on huge inventories, or pre-warm the cache with a full facts run |
| `group_by` enabled services (69 items) | `site.yml:21-95` | all | H (deploy-host CPU) | N × 69 | templating each item | none needed below ~1,000 hosts; it *saves* time later by eliminating disabled plays |
| `common` config + check | `roles/common/tasks/config.yml`, `check-containers.yml` | every host, in the first matching play | H × ~18 invocations | N | 3 container checks (`docker exec` each) + ~12 templates/files | `--limit` batches; it cannot be skipped selectively (`-t common` is a no-op) |
| `nova-cell` config | `roles/nova-cell/tasks/config.yml` | computes + conductors | C × ~24 invocations (with `config-host.yml` and its `module-load` include) | C | `merge_configs` renders `nova.conf.j2` **on the deploy host for every compute**; per-item template loops | Deploy-host CPU (more cores, fewer forks than cores × ~2); `--limit` |
| `nova-cell` check-containers | `check-containers.yml` | computes | C×S (3 containers) | 3C `docker exec` | `kolla_set_configs --check` starts a Python process in each container | – |
| Compute registration wait | `nova-cell/tasks/wait_discover_computes.yml` | first compute of each batch, delegated to conductor | D per batch | up to 20 × 10 s per batch; **multiplied by the number of batches when `serial` is used** | waits until *all* computes of the batch appear in `compute service list` | Keep batches large for this play, or run it once at the end |
| `discover_hosts --by-service` | `discover_computes.yml` | conductor[0] | D per batch | cell size (it scans services) | one nova-manage call per batch | – |
| Keystone registration | `service-ks-register` | first host | D per play/batch | per service (×5 retries max) | runs `ansible` inside `kolla_toolbox` (container exec + Python startup) | – |
| DB-sync bootstrap containers | `<role>/tasks/bootstrap_service.yml` | first host | D (per batch with serial) | per service | container create + DB migration check | Skip by using `deploy-containers` for config-only applies |
| OVS post-config | `roles/openvswitch/tasks/post-config.yml` | network + computes | C (1 `docker exec`, `Set system-id`; the bridge check `kolla_ensure_openvswitch_configured` runs on network hosts, and on computes only when `computes_need_external_bridge` is true: DVR, provider networks or OVN distributed FIP) | C | always runs; `Set system-id` always "changed" | – |
| Neutron config-host | `roles/neutron/tasks/config-host.yml` | network + computes | C | C | module load, sysctl | – |
| Neutron config + check | `roles/neutron/tasks/config.yml` | network + computes + controllers | C × ~5 | C | `merge_configs` of `neutron.conf` and `openvswitch_agent.ini` per host | – |
| Image pull | `service-images-pull` | every host | C×S (11 images per compute with the default services and Cinder LVM, [§2](#2-work-per-compute-host-read-from-the-task-files)) | C × image size | registry bandwidth, disk I/O, layer extraction | Local registry mirror close to the computes; pre-pull before maintenance; `--forks` to cap registry load |
| Container (re)creation | handlers | notified hosts | Cond, C×S | number of drifted containers | stop (10 s max), rm, create, start; `kolla_set_configs` on start | Batch with `--limit`/serial; avoid unnecessary drift ([§5](#5-why-a-small-change-becomes-a-large-workload)) |
| nova-libvirt restart | nova-cell handler | computes | Cond (any nova-compute drift) | C | `retries: 5`; SASL user re-creation after it | Avoid compute-side drift; batch |
| Fluentd/cron/toolbox restart | common handlers | all hosts reached | Cond (any service enabled/disabled) | N | – | Batch fleet-wide changes |
| `/etc/hosts` template | `roles/baremetal` (`bootstrap-servers`) | all | H, content O(N) | **N²** templating | loops over every baremetal host | Run `bootstrap-servers` only when adding hosts |
| Docker daemon restart | `roles/baremetal/tasks/post-install.yml:231-237` | all | Cond | N simultaneous | restarts every container on the host | `-e kolla_serial=…` with `bootstrap-servers` |
| SSH connection setup | Ansible ssh connection plugin | all | H (handshake once per host, again after 60 s idle) | invocations × SSH round trips | Ansible 2.9 already multiplexes connections without any `ansible.cfg` (default `ssh_args = -C -o ControlMaster=auto -o ControlPersist=60s`). Kolla ships no `ansible.cfg`, so `pipelining` stays off and each invocation still makes several round trips (tmp dir, transfer, exec, cleanup) | `pipelining = True` (requires no `requiretty`). On large fleets, a longer persistence such as `ssh_args = -C -o ControlMaster=auto -o ControlPersist=30m` |
| Certificate distribution | `service-cert-copy` (when `kolla_copy_ca_into_containers`) | every service config dir | C×S | per service | `copy` per service dir | Only enable when needed |

---

## 4. Performance model for 10 / 50 / 100 / 200 / 500 computes

### 4.1 Model

For a play whose tasks all run on the compute group (the nova-cell, openvswitch and neutron plays are dominated by
it):

```text
T_play ≈ Σ_tasks [ ceil(H_task / F_eff) × items_task × t_inv ]      (remote work, per-task barrier)
       + Σ_tasks [ H_task × t_render_task / P ]                       (deploy-host templating, P cores)
       + Σ_delegated/run_once steps                                    (constant per batch)
       + T_handlers (if drift)                                         (≈ max over hosts of restart time)
```

- `H` = hosts in the play (computes + the few others).
- `F_eff` = min(forks, what the deploy host CPU and SSH can sustain).
- `t_inv` = latency of one remote module invocation: SSH round trips, AnsiballZ transfer, Python start, `sudo`. The
  sources do not give it [NOT AVAILABLE]; it depends on your environment (the median per-task time on a single host,
  from `-vvv` timestamps or the `profile_tasks` callback).
- `t_render` = deploy-host CPU time to render a template for one host [NOT AVAILABLE].

Because of the per-task barrier, the critical path of a play is **(number of executed task-items on the slowest host) ×
⌈H/F⌉ waves**. Adding computes adds waves, not tasks.

### 4.2 Operation counts by fleet size

Built from the per-compute counts read from the code in [§2](#2-work-per-compute-host-read-from-the-task-files) [CODE].
Columns whose per-compute count the sources do not give are marked n/a [NOT AVAILABLE]. The "Waves per task" columns
give ⌈C/F⌉ for compute hosts at F = 20, 50 and 100; the worked examples below use F = 50. The waves multiply the
per-host invocation chain, they do not add tasks.

| Computes (C) | Compute task results, full `reconfigure` (per-compute count n/a) | Compute remote invocations, full `reconfigure` (per-compute count n/a) | `kolla_set_configs --check` execs on computes (11·C) | Compute task results, `-t nova` (per-compute count n/a) | Invocations, `-t nova` (46·C) | Waves per task at F=20 | Waves per task at F=50 | Waves per task at F=100 | Image pulls for a full image update (11·C) | Delegated fact `setup` calls with `--limit <1 host>` (*N* − 1 = C + 7 with 8 non-compute hosts, localhost included) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | n/a | n/a | 110 | n/a | 460 | 1 | 1 | 1 | 110 | 17 |
| 50 | n/a | n/a | 550 | n/a | 2,300 | 3 | 1 | 1 | 550 | 57 |
| 100 | n/a | n/a | 1,100 | n/a | 4,600 | 5 | 2 | 1 | 1,100 | 107 |
| 200 | n/a | n/a | 2,200 | n/a | 9,200 | 10 | 4 | 2 | 2,200 | 207 |
| 500 | n/a | n/a | 5,500 | n/a | 23,000 | 25 | 10 | 5 | 5,500 | 507 |

Reading the table:

- **No-change `-t nova reconfigure`, C=500, F=50.** Each compute runs a chain of 46 remote invocations. With 10
  waves per task, the compute-side critical path is ≈ **460 × t_inv** plus deploy-host templating
  (500 × nova.conf renders) and the constant delegated steps. Nothing restarts, and yet the run still costs
  ~23,000 remote invocations and 3,000 `docker exec` config checks (6 per compute).
- **The same run after a global change** (e.g. `enable_barbican`) adds a handler phase: 500 × (nova_ssh + nova_libvirt
  + nova_compute + 3 common containers) = **3,000 container restarts**, all in the same flush unless batched.
- **Image updates multiply data volume.** A tag change downloads 11 images per compute: 5,500 image pulls at C=500.
  Registry egress ≈ C × Σ(size of the new layers); image sizes are [NOT AVAILABLE]
  ([Q8](../troubleshooting/open-questions.md#q8) in [Findings](../reference/findings.md)). With the default
  `forks`/serial, this traffic is concurrent across up to `forks` hosts.
- **Fact gathering with `--limit`.** Gathering the 507 other hosts serially from one host costs ≈507 × t_setup before
  any real work. Fact caching removes it.

### 4.3 What is constant, per batch, or per host

| Constant (D) | Per batch (with `serial`) | Per controller | Per compute | Per container | Conditional |
|---|---|---|---|---|---|
| Keystone registration, DB create/grant, DB-sync containers, cell create/update, `map_cell0`, haproxy frontend rendering (per haproxy host) | all `run_once` steps above, compute registration wait (≤200 s), `discover_hosts` | API configs, MariaDB/RabbitMQ rolling restarts (per DB/MQ node) | facts, `group_by`, common, config-host, nova-cell/OVS/neutron config, OVS post-config | `compare_container` exec, image pull, restart/recreate | handlers (drift), image download (new image), `update_cell` (URL change), Docker restart (`daemon.json` change) |

---

## 5. Why a small change becomes a large workload

Two independent multipliers apply:

1. **Work multiplier (always).** Every run that includes the `compute` group executes the full per-host chain on
   every compute, even with no change ([§2](#2-work-per-compute-host-read-from-the-task-files)): config re-rendering and
   comparison, container config checks, common role, sysctl and modules, OVS post-config, discovery. **Kolla has no
   "only if changed" short-circuit at play level.**
2. **Restart multiplier (when inputs are global).** Global inputs are rendered into every compute's files ([Component
   dependencies §5](../components/dependencies.md#5-compute-node-dependency-summary)). Loop-notify widens a single
   drifted container to the whole role on that host ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). Without `serial`,
   all restarts land in one handler flush.

---

## 6. Scaling at 3, 10 and 30 computes, read from the code

The scenarios of [§2](#2-work-per-compute-host-read-from-the-task-files) at 3, 10 and 30 computes, for an inventory with
3 controllers, 2 network nodes, 1 storage node, 1 monitoring node and localhost. Counts on computes come from
[§2](#2-work-per-compute-host-read-from-the-task-files) [CODE]. Cells marked n/a are [NOT AVAILABLE]: the sources give
neither task-result totals, nor the non-compute part of the fleet counts, nor durations.

| Scenario | Computes | forks | Task results (fleet) | per compute | `compare_container` calls on computes | Restarts/recreates | nova-cell play duration | Total duration |
|---|---|---|---|---|---|---|---|---|
| `deploy` (first time) | 3 | 20 | n/a | n/a | 33 (no check exec) | n/a | n/a | n/a |
| `deploy` (first time) | 10 | 20 | n/a | n/a | 110 (no check exec) | n/a | n/a | n/a |
| `deploy` (first time) | 30 | 20 | n/a | n/a | 330 (no check exec) | n/a | n/a | n/a |
| `-t nova reconfigure` (no change) | 3 | 20 | n/a | n/a | 18 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change) | 10 | 20 | n/a | n/a | 60 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change) | 30 | 20 | n/a | n/a | 180 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change), forks 5 | 30 | 5 | n/a | n/a | 180 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change), forks 50 | 30 | 50 | n/a | n/a | 180 | 0 | n/a | n/a |
| `-t nova reconfigure` with a nova-compute-only override | 30 | 20 | n/a | n/a | 180 | **90** (30 × nova_compute + nova_libvirt + nova_ssh) | n/a | n/a |
| `-t nova reconfigure --limit compute001` (no change) | 30 | 20 | n/a | n/a | 6 | 0 | n/a | n/a |

What the code shows:

1. **Per-compute work is constant and fleet work is linear.**
   - Every compute runs the same task files for the same services
     ([§2](#2-work-per-compute-host-read-from-the-task-files)), so the per-compute counts do not depend on C and the
     compute part of every fleet count grows by the per-compute count. The per-compute task-result counts for a deploy
     and a `-t nova` run are [NOT AVAILABLE].
   - The number of `compare_container` calls grows by 11 per compute for a deploy and 6 per compute for `-t nova`.
     A call runs `docker exec kolla_set_configs --check` only when the container exists and no other attribute
     differs (`kolla_docker.py:326-332`). On a first-time deploy every container is missing, so no check exec runs;
     a no-change run does one exec per call [CODE].
   - forks changes none of these counts: it only bounds how many hosts run a task at once
     (ansible 2.9.27 `lib/ansible/executor/task_queue_manager.py:257-258`) [CODE].
2. **The compute-wide plays grow with C.**
   - The plays that run on every compute include chrony (with common), nova-cell, openvswitch and neutron
     (`docs/day2/ussuri/reference/listings/list-tasks-nova.txt:127, :226, :268, :280`; `compute` is in the chrony and
     openvswitch
     groups: `inventory/multinode:50-55, :144-147`) [CODE]. The share of run time they take as C grows is
     [NOT AVAILABLE].
3. **forks and the deploy host's CPU.**
   - Whether, and at which forks value, the deploy host's CPU becomes the bottleneck is [NOT AVAILABLE]
     ([Q7](../troubleshooting/open-questions.md#q7) in [Findings](../reference/findings.md)).
   - What runs on the deploy host is in the code [CODE]: one worker process per fork (ansible 2.9.27
     `lib/ansible/executor/task_queue_manager.py:257-258`, `lib/ansible/plugins/strategy/__init__.py:387-390`),
     module packaging (AnsiballZ) for every invocation
     (ansible 2.9.27 `lib/ansible/plugins/action/__init__.py:155, :206`), templating of `nova.conf.j2`
     (`ansible/action_plugins/merge_configs.py:151-161`) and the per-host `group_by` loop (`site.yml:21-95`).
   - Whether forks overlap SSH and remote-execution latency in production, and up to which point, is
     [NOT AVAILABLE].
   - Size the deploy host (cores) together with forks.
4. **A small change restarts the fleet in one step** [CODE]. With one nova-compute-only override on 30 computes,
   loop-notify ([Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code))
   notifies `nova_compute`, `nova_libvirt` and `nova_ssh` on every compute: 90 container restarts. Without `serial` all
   30 computes are in one batch (`nova.yml:132`, `serial` defaults to "0"; ansible 2.9.27
   `lib/ansible/executor/playbook_executor.py:161-169, :263-264, :276-278`), so the restarts run at one handler flush
   (`roles/nova-cell/tasks/deploy.yml:21-22`), on at most `forks` hosts at a time (ansible 2.9.27
   `lib/ansible/plugins/strategy/__init__.py:359-391, :1019-1035`). How close together they land in time is
   [NOT AVAILABLE].
5. **`--limit` bounds the restarts, but fact gathering stays O(inventory)** [CODE].
   - With `--limit compute001` on the 30-compute inventory (38 hosts, localhost included), compute001 runs
     **38 `setup` calls in sequence**: its own (`gather-facts.yml:10-15`), plus one delegated call for each of the
     37 other inventory hosts (`gather-facts.yml:29-50`). The delegated loop runs its items one after another
     (ansible 2.9.27 `lib/ansible/executor/task_executor.py:317, :367`). Its duration is [NOT AVAILABLE].
   - The delegated `discover_hosts`/`list_cells` work runs on the first conductor, control01
     (`roles/nova-cell/tasks/wait_discover_computes.yml:41-42`, `discover_computes.yml:21`).
   - With SSH, multiply the delegated count by the real per-host `setup` time; at 500 computes it is ≈508 sequential
     fact gatherings before any work starts.

---

## 7. Influence of the main variables

| Variable | Effect | Guidance |
|---|---|---|
| **Ansible forks** | Divides the number of waves per task (⌈H/F⌉). Bounded by deploy-host CPU (templating, AnsiballZ build per invocation) and memory (one worker process per fork) | Raise until deploy-host CPU saturates; where that happens is [NOT AVAILABLE] ([§6](#6-scaling-at-3-10-and-30-computes-read-from-the-code)). Size the deploy host for templating |
| **Serial (`kolla_serial`)** | Bounds simultaneous *restarts* per play, but **adds** time: every batch re-runs `run_once` steps and the compute registration wait, and each batch waits for the slowest host | Use it for restart safety on changes with drift, not for no-change runs. Prefer `genconfig` + `deploy-containers --limit` batches |
| **Task delegation** | `delegate_to` steps serialise on one host (conductor[0], neutron-server[0], rabbitmq[0]) | That host's health gates the whole run |
| **SSH overhead** | Each remote invocation pays several SSH round trips (tmp dir, transfer, exec, cleanup). The connection itself is reused: Ansible 2.9 defaults to `ControlMaster=auto` with `ControlPersist=60s`, so a new handshake happens only after a host has been idle for 60 s | `pipelining = True` (requires no `requiretty` in sudoers) is the main lever. On large fleets, a longer `ControlPersist` (keep `-C -o ControlMaster=auto` in `ssh_args`) and a short `ControlPath` |
| **Docker image size** | Pull time and disk I/O per host | Local registry, pre-pull, avoid unnecessary tag churn |
| **Network bandwidth** | Concurrent pulls from up to `forks` hosts | Cap with `--forks` during `pull`; registry caching |
| **Disk I/O** | Image extraction, container creation, `/etc/kolla` writes | SSD for `/var/lib/docker` |
| **Container startup time** | Handlers wait for `docker start` (not for service readiness), except explicit waits (haproxy, OVS DB, MariaDB WSREP, RabbitMQ) | – |
| **Handler execution** | Runs at the flush in parallel; the 10 s SIGKILL bounds stop time | Batch to bound the blast radius |
| **Parallel vs sequential** | Hosts run in parallel within a task; items and tasks run sequentially per host; plays are sequential | Reduce items (disable unused services), use tags to skip plays, use `--limit` to skip hosts |

---

## 8. Bottlenecks and optimisation opportunities (ranked)

1. **Avoid running compute-wide plays when you do not need them.**
   - Use `-t nova-api` for API-only changes (no computes).
   - Use `--limit` for host-scoped changes.
   - Use `--skip-tags haproxy` when frontends are not changing.
2. **Separate config from apply.** `genconfig` once, then `deploy-containers --limit <batch>`. With `-t nova`, the
   apply step on a compute runs only `setup` and the `check-containers.yml` loops of common and nova-cell
   (7 invocations instead of 46 for `-t nova reconfigure`, [§2](#2-work-per-compute-host-read-from-the-task-files)), and
   runs no bootstrap or Keystone steps [CODE: `roles/common/tasks/deploy-containers.yml:2`,
   `roles/nova-cell/tasks/deploy-containers.yml:2`, `roles/nova/tasks/deploy-containers.yml:2`, `nova.yml:49-51,
   :85-87`].
3. **Fact caching + setup filter.** This removes the O(N) serial delegated gathering under `--limit` and speeds the
   first play. All options are documented in Ussuri `ansible-tuning.rst`.
4. **SSH pipelining** cuts the per-invocation constant that multiplies 46–53 invocations per compute in a `-t nova`
   run (the count for a full run is [NOT AVAILABLE]). A longer `ControlPersist` than the 60 s default avoids
   repeated handshakes on large fleets.
5. **Size forks to the deploy host.** Templating of large Jinja templates (`nova.conf.j2`, `neutron.conf.j2`) happens
   on the deploy host, per compute.
6. **Pre-pull images** (`kolla-ansible pull`) before upgrade windows, from a nearby registry.
7. **Minimise global drift.**
   - Batch `enable_*` changes.
   - Avoid touching RabbitMQ/memcached membership casually.
   - Keep compute-relevant overrides in `nova/nova-compute.conf` rather than the global `nova.conf`.
   - Do not put server-only ML2 options in `neutron/ml2_conf.ini`.
8. **Keep batches large for the nova-cell play when using serial.** The compute registration wait and discovery run
   once per batch.
9. **Disable services you do not use.** The `group_by` optimisation removes their plays entirely (`site.yml:4-6`).
   Every enabled service adds tasks to the common role and to every host in its groups.

## Related

- [Execution flow §5](deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) (batching)
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) (small change, large workload)
- [Write config first, apply in controlled batches
  §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern) (batched
  compute changes)
- [Open questions](../troubleshooting/open-questions.md) ([Q7](../troubleshooting/open-questions.md#q7),
  [Q8](../troubleshooting/open-questions.md#q8): timings and image sizes)
- [Kolla-Ansible Academy](../index.md)
