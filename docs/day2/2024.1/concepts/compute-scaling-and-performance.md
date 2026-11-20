---
title: Compute scaling and performance
description: Which Kolla-Ansible 2024.1 operations grow with the number of compute nodes, why, and how to bound them.
tags: [scaling, nova, limit, serial, facts, loop-notify, pull, images]
remember:
  - "With the default linear strategy, a task is queued for every host that has it next, and the next task starts only when all of them have finished: the slowest host sets the pace. <span class=\"ev ev-code\">CODE</span>"
  - "Adding computes adds waves, not tasks: a task on H hosts needs ⌈H/F⌉ waves, F being <code>forks</code> (one worker per fork, at most the batch size)."
  - "In 2024.1 a no-change <code>-t nova reconfigure</code> makes 27 remote invocations per compute (one more than 2023.1: the new <code>hostnqn</code> file) and 3 <code>compare_container</code> calls. <span class=\"ev ev-code\">CODE</span>"
  - "<code>--limit</code> bounds the restarts, but fact gathering stays O(inventory): one limited host gathers the facts of every other host, one after another. <span class=\"ev ev-code\">CODE</span>"
  - "<code>serial</code> bounds simultaneous restarts per play, but adds time; <code>max_fail_percentage</code>, now on every play, stops nothing early at its default of 100. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "Does this study give how long a run takes?"
    options: ["Yes, measured on a lab", "No: work is counted as operations read from the source"]
    answer: 1
    explain: "Task-result totals and wall times are NOT AVAILABLE: nothing was run against a host."
    see: "2-work-per-compute-host-read-from-the-task-files"
  - q: "How many remote module invocations does a no-change <code>-t nova reconfigure</code> make on one compute in 2024.1 (default services, Cinder LVM, kvm, non-Ubuntu host)?"
    options: ["26, as in 2023.1", "27: the new <code>hostnqn</code> template adds one", "About 50, because the common role runs too"]
    answer: 1
    explain: "The nova-cell <code>config.yml</code> gained the <code>hostnqn</code> template for nova_compute; the common play is tagged <code>common</code> only and does not run under <code>-t nova</code> <span class=\"ev ev-code\">CODE</span>. compute001 makes 31, with the delegated discovery steps."
    see: "2-work-per-compute-host-read-from-the-task-files"
  - q: "What do more computes add to a play?"
    options: ["More tasks on each host", "More waves: ⌈H/F⌉, with H hosts and F forks"]
    answer: 1
    explain: "The critical path of a play is the number of executed task-items on the slowest host × ⌈H/F⌉ waves."
    see: "41-model"
  - q: "Does <code>--limit</code> reduce fact gathering?"
    options: ["Yes, facts are gathered only on the limited hosts", "No: <code>--limit</code> bounds the restarts, but fact gathering stays O(inventory)"]
    answer: 1
    explain: "Without a fact cache, the limited hosts gather the facts of every other inventory host in a delegated loop whose items run one after another <span class=\"ev ev-code\">CODE</span>."
    see: "6-scaling-at-3-10-and-30-computes-read-from-the-code"
---

# Compute scaling and performance

Which Kolla-Ansible 2024.1 operations grow with the number of compute nodes, why, and how to bound them.

> [!NOTE]
> **Key answers**
>
> - **No timings are given.** Work is counted as operations read from the source; task-result totals and wall times are
>   [NOT AVAILABLE] ([§2](#2-work-per-compute-host-read-from-the-task-files), [§4.1](#41-model)).
> - **Per compute, for the default 2024.1 service set with Cinder LVM, `nova_compute_virt_type: kvm`, the Docker engine
>   and a non-Ubuntu host, a no-change `-t nova reconfigure` makes 27 remote module invocations (31 on compute001) and 3
>   `compare_container` calls; a full `deploy` or `reconfigure` makes 10 `compare_container` calls** [CODE]
>   ([§2](#2-work-per-compute-host-read-from-the-task-files)). Changed in 2024.1: one invocation more than 2023.1
>   (26, 30 on compute001), from the new `hostnqn` file of nova_compute (`roles/nova-cell/tasks/config.yml:203-216`).
>   The `common` play still does not run under `-t nova` (`site.yml:88-103`).
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
> [NOT AVAILABLE] covers, for example, task-result totals and wall times. Citations that start with `lib/ansible/` are
> read in ansible-core 2.16.20, the version studied for 2024.1 (`tools/kolla-ansible:10-11` accepts 2.15 to 2.16;
> 2.15 is not studied).

---

<a id="1-how-ansible-29-spends-time-in-kolla-ansible"></a>
<a id="1-how-ansible-core-214-spends-time-in-kolla-ansible"></a>

## 1. How ansible-core 2.16 spends time in Kolla-Ansible

| Factor | Mechanism | Consequence for Kolla |
|---|---|---|
| **Linear strategy (default)** | The strategy takes the next task of the play and queues it for **every host whose next task it is** (up to `forks` at a time), then **waits until all queued results are back before it moves to the next task** [CODE: ansible-core 2.16.20 `lib/ansible/plugins/strategy/linear.py:50-93` (next task in lockstep), `:119`, `:129-198` (queue for each host), `:217-219` (wait for the results)] | The slowest host sets the pace of every task. One slow compute (disk, SSH, container engine) slows the whole fleet |
| **forks** (Ansible default 5; Kolla's `doc/source/user/ansible-tuning.rst:20-34` raises it to 20 as an example) | Max parallel host executions per task: the task queue manager creates `min(forks, batch size)` worker slots for each play run, and each queued host/task takes a free slot [CODE: ansible-core 2.16.20 `lib/ansible/executor/task_queue_manager.py:144`, `:174-178`, `:320-321`; `lib/ansible/plugins/strategy/__init__.py:387-419`; default 5: `lib/ansible/config/base.yml:639-641`] | A task on *H* hosts needs ⌈H/F⌉ waves |
| **Loops** (`with_dict: <role>_services`, `with_items`) | Items run **sequentially on each host** [CODE: ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:288`, `:336`]; each item that passes its `when` is a separate module execution (separate remote command); skipped items run no module | `config.yml` and `check-containers.yml` cost *items × invocation latency* per host |
| **Remote module invocation** | Without pipelining (off by default: ansible-core 2.16.20 `lib/ansible/config/base.yml:113-115`), each invocation = SSH exec to create a tmp dir, transfer the AnsiballZ payload, run it, clean up. With `become`, `sudo` is added | The fixed cost per invocation dominates idempotent runs |
| **Deploy-host templating** | `template` and `merge_configs` render **on the deploy host** for every host and item, then `copy` compares checksums remotely [CODE: `ansible/action_plugins/merge_configs.py:149-165, :208-216`; ansible-core 2.16.20 `lib/ansible/plugins/action/template.py:152`, `:185-192`, `lib/ansible/plugins/action/copy.py:263, :285`] | Deploy-host CPU scales with hosts × templates. `nova.conf.j2` and `neutron.conf.j2` are large, with loops over groups |
| **Controller-side tasks** | `group_by`, `set_fact`, `include_*`, `meta` run in Ansible workers without SSH | Cheap per host, but not free: the 50-item `group_by` loop (`site.yml:20-74`; 56 items in 2023.1) is templated in a deploy-host worker for every host, and `group_by` runs no module on the host [CODE: ansible-core 2.16.20 `lib/ansible/plugins/action/group_by.py:30-52`]. Its CPU cost per host is [NOT AVAILABLE] |
| **`run_once` / `delegate_to`** | Run once (per batch) on one host: the linear strategy queues a `run_once` task for the first host and stops there [CODE: ansible-core 2.16.20 `lib/ansible/plugins/strategy/linear.py:181`, `:208-209`] | Constant cost unless `serial` multiplies it |
| **Handlers** | Run at flush points on notified hosts: `flush_handlers` switches the notified hosts to the handlers state, and the linear strategy inserts the play's handlers in its task list and queues each one like a task, in parallel up to `forks` [CODE: ansible-core 2.16.20 `lib/ansible/plugins/strategy/__init__.py:952-963`, `lib/ansible/plugins/strategy/linear.py:90-91`, `:129-198`] | Restart time of the slowest container on the slowest host |
| **`until`/`retries` loops** | e.g. compute registration wait (`retries: 20`, `delay: 10`: `roles/nova-cell/tasks/wait_discover_computes.yml:27-28`), Keystone registration retries (5 × 10 s: `roles/service-ks-register/defaults/main.yml:38, :40`), `wait_for` | `retries: n` means up to n + 1 attempts and n sleeps of `delay` per task, plus the time of each attempt [CODE: ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:627-639`, `:768-790`]; how many attempts a run needs is [NOT AVAILABLE] |
| **Fact gathering** | `setup` on every host at the start, skipped when facts are already cached (`gather-facts.yml:19-25`). With `--limit`, the limited hosts gather **all other hosts' facts sequentially** in a delegated loop, the hosts being divided between the limited hosts (`gather-facts.yml:34-62`) | O(total hosts) serial latency per limited run without fact caching |
| **`max_fail_percentage`** (new on every play in 2024.1) | Every play now sets `max_fail_percentage: <service>_max_fail_percentage \| default(kolla_max_fail_percentage) \| default(100)` (e.g. `gather-facts.yml:7-10`, `site.yml:96-99`, `nova.yml:141-144`). The check breaks the play only when the failed hosts of the current batch exceed that percentage of the batch [CODE: ansible-core 2.16.20 `lib/ansible/plugins/strategy/linear.py:336-350`; the failed-host list is cleared for each batch, `lib/ansible/executor/task_queue_manager.py:330-338`] | At the default 100 it never stops a play early: one failed or slow compute does not stop the others. Setting a lower value is an operator choice; its effect on a given run is [NOT AVAILABLE] |

---

## 2. Work per compute host (read from the task files)

Counts below are read from the task files of the roles that run on a compute [CODE], for the default 2024.1 service
set with Cinder LVM (`enable_cinder` and `enable_cinder_backend_lvm` set; this adds `iscsid` on computes:
`group_vars/all.yml:750, :753-754, :794`, `roles/iscsi/defaults/main.yml:3-6, :62-67`, `inventory/multinode:305-308`),
`nova_compute_virt_type: kvm` (`group_vars/all.yml:1127`), the Docker engine (`kolla_container_engine: "docker"`,
`group_vars/all.yml:92`) and a non-Ubuntu host (Ubuntu adds one `systemd` call:
`roles/nova-cell/tasks/config-host.yml:44-53`). Task-result totals depend on how skipped tasks, includes and `meta`
tasks are counted at run time; the sources do not give them [NOT AVAILABLE].

- A "task result" is one task × one host, including skipped tasks.
- A "remote invocation" is one module execution on the host, counting each executed loop item. Loop items skipped by
  `when` run no module and are not counted (for example, on a compute 5 of the 8 items of each `nova_cell_services`
  loop are skipped: `roles/nova-cell/defaults/main.yml:2-72`). A `with_first_found` task whose files are all absent
  (`skip: true`) has no item and runs no module (`roles/nova-cell/tasks/config.yml:24-34, :184-201`).
- Controller-only work is excluded from the invocation count: `group_by`, `set_fact`, `fail`, `include_*`, `meta`.
- Each `template`, `copy` or `merge_configs` item counts as one invocation, although the copy action behind them runs
  two modules on the host when the file is unchanged (remote `stat`, then `file`) [CODE: ansible-core 2.16.20
  `lib/ansible/plugins/action/copy.py:263, :285, :380`]. SSH round trips are therefore higher than the invocation
  count.
- Where two figures are given, the higher one is compute001, the first host of the nova-cell play (`compute` is its
  first host pattern: `nova.yml:125-134`). It also runs the delegated `run_once` steps: compute discovery on the first
  conductor, control01 (3 invocations: `roles/nova-cell/tasks/wait_discover_computes.yml:8-43`,
  `get_cell_settings.yml:2-21`, `discover_computes.yml:14-21`) and one `stat` of `vendordata.json` on the deploy host
  (`roles/nova-cell/tasks/config.yml:43-48`).
- The `common` role is not part of a `-t nova` run: it has its own play, tagged `common` only (`site.yml:88-103`),
  and the nova-cell role has no `meta` dependency on it (the role has no `meta/` directory). **Changed in 2024.1:** its
  invocations per host are 20 instead of 18. They are 3 config directories, 8 templates, the new `ensure_image` of the
  fluentd image and `docker_image_info` of it (to read the `fluentd_binary`/`fluentd_user` labels), 2 ownership fixes,
  3 `compare_container`, and the `kolla_logs` volume and its link (`roles/common/tasks/config.yml:2-24, :42-63,
  :93-102, :140-323`, `check-containers.yml:2-17`, `bootstrap.yml:2-16`, with `enable_fluentd` and `enable_rabbitmq`
  true, `group_vars/all.yml:765, :732`). With Podman the label read uses `podman_image_info` and two more steps run
  (`/etc/tmpfiles.d/kolla.conf` and `systemd-tmpfiles --create`: `roles/common/tasks/config.yml:30-40, :73-83`).
  These run only when the `common` play runs (no tag or `-t common`).
- *N* is the number of inventory hosts in `groups['all']`, localhost included (`inventory/multinode:32-33`).

| Action | Task results per compute | Executed (non-skipped) | Remote module invocations per compute | `compare_container` calls per compute (one in-container `kolla_set_configs --check` exec each when the container exists) | Source |
|---|---|---|---|---|---|
| `deploy` (first time) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 10 calls, 0 execs (containers missing) | `check-containers.yml` of common (3), iscsi (1), openvswitch (2), neutron (1), nova-cell (3); `module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_docker_worker.py:146-181` |
| `deploy` (no change) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 10 | as above |
| `reconfigure` (no tag, no change) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 10 | as above |
| `-t nova reconfigure` (no change) | NOT AVAILABLE | NOT AVAILABLE | 27 (31 on compute001) | 3 (nova-cell only) | breakdown below |
| `-t nova reconfigure --limit compute001` (no change) | NOT AVAILABLE | NOT AVAILABLE | 31 + delegated fact loop (*N* − 1) | 3 | breakdown below; `gather-facts.yml:34-62` |
| `-t nova deploy-containers --limit compute001` (no change) | NOT AVAILABLE | NOT AVAILABLE | 4 (`setup` + 3 `compare_container`) + delegated fact loop (*N* − 1) | 3 | `roles/nova-cell/tasks/deploy-containers.yml:2`, `roles/nova-cell/tasks/check-containers.yml:2-22` |
| `pull` (all) | NOT AVAILABLE | NOT AVAILABLE | 11 (`setup`, 10 image pulls) | 0 | `roles/service-images-pull/tasks/main.yml:2-18` (one `pull_image` per enabled service mapped to the host) |
| `-t haproxy reconfigure` | 4 (facts + group_by only) | 4 | 1 (`setup`) | 0 | plays tagged `always`: `gather-facts.yml:5-26, :34-62` (the second play targets only limited hosts), `site.yml:7-75`; `site.yml:105-118` (the only play tagged `haproxy`, the loadbalancer play, targets the `loadbalancer` group) |

The 10 per compute: `fluentd`, `kolla_toolbox`, `cron` (`roles/common/defaults/main.yml:3-27`), `iscsid`
(`roles/iscsi/defaults/main.yml:3-6`), `openvswitch_db` and `openvswitch_vswitchd`
(`roles/openvswitch/defaults/main.yml:3-34`), `neutron_openvswitch_agent` (`roles/neutron/defaults/main.yml:26-48`;
the other neutron agents are off on a compute by default, e.g. `neutron_enable_ovn_agent: "no"`,
`group_vars/all.yml:1119`), `nova_libvirt`, `nova_ssh`, `nova_compute` (`roles/nova-cell/defaults/main.yml:3-63`).
The same list drives the 10 image pulls. Still holds in 2024.1.

Breakdown of the 27 remote invocations of a no-change `-t nova` run on one compute, read from the task files [CODE]
(compute001 adds 4 delegated invocations, for 31):

| Kind | Invocations | Source |
|---|---|---|
| `template` items (module-load persistence, udev rule, config.json ×3, libvirt ×2, SASL ×3, ssh files ×4, **`hostnqn`**) | 15 | module-load, nova-cell `config-host.yml` + `config.yml` (`roles/module-load/tasks/main.yml:18-27`; `roles/nova-cell/tasks/config-host.yml:30-39`; `roles/nova-cell/tasks/config.yml:56-67, :106-121, :130-148, :150-167, :203-216`; `libvirt_enable_sasl: true`, `roles/nova-cell/defaults/main.yml:569`) |
| `file` items (config dirs ×3) | 3 | nova-cell (`roles/nova-cell/tasks/config.yml:2-13`) |
| `kolla_container` (compare_container ×3, remove_volume `nova_libvirt_secrets`) | 4 | nova-cell (`roles/nova-cell/tasks/check-containers.yml:2-22`; `roles/nova-cell/tasks/post-config.yml:3-8`, imported by `deploy.yml:39`) |
| `merge_configs` (nova.conf ×1 on a compute) | 1 | nova-cell `config.yml` (`roles/nova-cell/tasks/config.yml:69-89`; `roles/nova-cell/defaults/main.yml:485-491`) |
| `sysctl` ×2, `modprobe`, `setup` | 4 | facts, module-load, nova-cell `config-host.yml` (`gather-facts.yml:19-25`; `roles/module-load/tasks/main.yml:8-16`; `roles/nova-cell/tasks/config-host.yml:11-24`) |

Compared with 2023.1 (26, 30 on compute001): the only new invocation is the `hostnqn` template, rendered for every
compute from its host name (`roles/nova-cell/tasks/config.yml:203-216`, `templates/hostnqn.j2:1`). `config-host.yml`,
`module-load`, `check-containers.yml` and `wait_discover_computes.yml` are unchanged apart from the module name
(`kolla_docker` → `kolla_container`). The `nova.conf` merge reads one more optional source,
`<node_custom_config>/nova/<host>/<service>.conf` (`roles/nova-cell/tasks/config.yml:80`), a deploy-host file lookup
that adds no invocation. Discovery now runs `exec -t` (`roles/nova-cell/tasks/discover_computes.yml:17`).

> [!NOTE]
> "No change" means a cloud already deployed with 2024.1 code. The first 2024.1 run after an upgrade from 2023.1 is
> not a no-change run, for two reasons read in the code [CODE]: the systemd unit template changed
> (`module_utils/kolla_systemd_worker.py:20-39`) and `compare_container` compares the whole unit file text
> (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_systemd_worker.py:154-167`), so a container
> whose unit was written by 2023.1 code is reported as changed; and `om_enable_rabbitmq_quorum_queues` now defaults
> to `true` (`group_vars/all.yml:268`), which adds `rabbit_quorum_queue = true` to the rendered `nova.conf`
> (`roles/nova-cell/templates/nova.conf.j2:207-216`) of a cloud that kept the 2023.1 default. The restarts that
> follow are counted in [§6](#6-scaling-at-3-10-and-30-computes-read-from-the-code) only for the override case.

Per-**controller** counts are [NOT AVAILABLE]. Controllers carry more roles than computes, but they are few.
Compute-side work is what scales.

### 2.1 Fleet totals scale linearly

Total task results ≈ `fixed + Σ_hosts per-host count`:

- **Full no-change `reconfigure`, 3 computes:** the fleet and per-compute task-result totals are [NOT AVAILABLE].
- **Each additional compute adds** [CODE, counts from [§2](#2-work-per-compute-host-read-from-the-task-files)]:
  - 10 `compare_container` calls (10 `kolla_set_configs --check` execs once its containers exist) to every full
    `deploy`/`reconfigure`; the task results and remote invocations it adds to a full run are [NOT AVAILABLE];
  - 27 remote invocations and 3 checks to every `-t nova` run; the task results it adds are [NOT AVAILABLE].

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
| Fact gathering (`setup`) | `gather-facts.yml:19-25` | all | H | ⌈N/F⌉ waves | full `setup` collects hardware, network (many interfaces with OVS/Neutron), mounts; facter/ohai if present | `kolla_ansible_setup_filter: "ansible_[!qt]*"` (skips `qvo`/`tap` interface facts), `kolla_ansible_setup_gather_subset` (both default to `omit`: `group_vars/all.yml:31, :37`), fact caching (`gathering = smart` + jsonfile; with cached facts the `setup` task is skipped: `gather-facts.yml:23-25`) — documented in `doc/source/user/ansible-tuning.rst:36-80, :106-140` |
| Delegated fact gathering under `--limit` | `gather-facts.yml:34-62` | limited hosts gather everyone | **N sequential per limited host** (N/L each) | O(N) serial | `delegate_to` loop runs items one after another | Fact cache; avoid `--limit` with a single host on huge inventories, or pre-warm the cache with `kolla-ansible gather-facts` without a limit (`doc/source/user/ansible-tuning.rst:68-85`) |
| `group_by` enabled services (50 items) | `site.yml:20-74` | all | H (deploy-host CPU) | N × 50 | templating each item | none needed below ~1,000 hosts; it *saves* time later by eliminating disabled plays (`site.yml:4-6`) |
| `common` config + check | `roles/common/tasks/config.yml`, `check-containers.yml`, `bootstrap.yml` | every host of the `common` play (`site.yml:88-103`) | H × 20 invocations ([§2](#2-work-per-compute-host-read-from-the-task-files)) | N | 3 container checks (`docker exec` each) + 13 templates/files + fluentd `ensure_image` and label read (new in 2024.1) + 2 bootstrap steps | `--limit` batches; the play is tagged `common` only, so any service tag (e.g. `-t nova`) skips it, `-t common` runs it alone, `--skip-tags common` removes it |
| `nova-cell` config | `roles/nova-cell/tasks/config.yml` | computes + conductors | C × 22 invocations (17 in `config.yml`, 5 in `config-host.yml` with its `module-load` include, [§2](#2-work-per-compute-host-read-from-the-task-files)) | C | `merge_configs` renders `nova.conf.j2` **on the deploy host for every compute**; per-item template loops | Deploy-host CPU (more cores, fewer forks than cores × ~2); `--limit` |
| `nova-cell` check-containers | `check-containers.yml` | computes | C×S (3 containers) | 3C `docker exec` | `kolla_set_configs --check` starts a Python process in each container | – |
| Compute registration wait | `nova-cell/tasks/wait_discover_computes.yml` | first compute of each batch, delegated to conductor | D per batch | up to 21 attempts with 20 × 10 s of sleep per batch; **multiplied by the number of batches when `serial` is used** | waits until *all* computes of the batch appear in `compute service list` | Keep batches large for this play, or run it once at the end |
| `discover_hosts --by-service` | `discover_computes.yml` | conductor[0] | D per batch | cell size (it scans services) | one nova-manage call per batch | – |
| Keystone registration | `service-ks-register` | first host | D per play/batch | per service (up to 6 attempts, 5 × 10 s of sleep: `roles/service-ks-register/defaults/main.yml:38, :40`) | runs `ansible` inside `kolla_toolbox` (container exec + Python startup) | – |
| DB-sync bootstrap containers | `<role>/tasks/bootstrap_service.yml` | first host | D (per batch with serial) | per service | container create + DB migration check | Skip by using `deploy-containers` for config-only applies |
| OVS post-config | `roles/openvswitch/tasks/post-config.yml` | network + computes | C (**3** `kolla_toolbox` items, `Set system-id, hostname and hw-offload`: `post-config.yml:3-23`; 2 in 2023.1, the `hostname` item is new. The bridge and port tasks, which now use the `openvswitch_bridge` and `openvswitch_port` modules instead of the image script, run on network hosts, and on computes only when `computes_need_external_bridge` is true: DVR, provider networks or OVN distributed FIP, `post-config.yml:25-53`, `group_vars/all.yml:1095`) | C | always runs; each item runs `ansible` inside the `kolla_toolbox` container (`library/kolla_toolbox.py:113-114, :163-165`) | – |
| Neutron config-host | `roles/neutron/tasks/config-host.yml` | network + computes | C | C | module load (`:2-13`), an IPv6 `sysctl -n` check on every host (`:15-18`), sysctl settings through the `sysctl` role only where the L3 agent runs (`:20-34`) | – |
| Neutron config + check | `roles/neutron/tasks/config.yml` | network + computes + controllers | C (per-compute count not established [NOT AVAILABLE]) | C | `merge_configs` of `neutron.conf` and `openvswitch_agent.ini` per host (`roles/neutron/tasks/config.yml:87-122, :198-213`) | – |
| Image pull | `service-images-pull` | every host | C×S (10 images per compute with the default services and Cinder LVM, [§2](#2-work-per-compute-host-read-from-the-task-files)) | C × image size | registry bandwidth, disk I/O, layer extraction | Local registry mirror close to the computes; pre-pull before maintenance; `--forks` to cap registry load |
| Container (re)creation | handlers | notified hosts | Cond, C×S | number of drifted containers | stop (up to `docker_graceful_timeout`, 60 s by default: `group_vars/all.yml:139`), rm, create, start; `kolla_set_configs` on start | Batch with `--limit`/serial; avoid unnecessary drift ([§5](#5-why-a-small-change-becomes-a-large-workload)) |
| nova-libvirt restart | nova-cell handler | computes | Cond (any nova-compute drift) | C | `retries: 5`; readiness check and SASL user re-creation after it (`roles/nova-cell/handlers/main.yml:92-142`) | Avoid compute-side drift; batch |
| Fluentd/cron/toolbox restart | common handlers | all hosts of the `common` play, only when that play runs | Cond (any service enabled/disabled) | N | – | Batch fleet-wide changes |
| `/etc/hosts` block | ansible-collection-kolla `roles/etc_hosts/tasks/etc-hosts.yml:25-41` (`bootstrap-servers`) | all | H, content O(N) | **N²** templating | loops over every `baremetal` host | Run `bootstrap-servers` only when adding hosts |
| Docker daemon restart | ansible-collection-kolla `roles/docker/handlers/main.yml:10-15`, notified by `roles/docker/tasks/config.yml:48-53` (`daemon.json`) | all | Cond | N simultaneous | `restarted` by default (`docker_systemd_reload: false`, `roles/docker/defaults/main.yml:65`); whether every container on the host stops is [NOT AVAILABLE] ([R14](../risk/risk-register.md#r14)) | `-e kolla_serial=…` with `bootstrap-servers` (`kolla-host.yml:6`) |
| SSH connection setup | Ansible ssh connection plugin | all | H (handshake once per host, again after 60 s idle) | invocations × SSH round trips | ansible-core already multiplexes connections without any `ansible.cfg` (default `ssh_args = -C -o ControlMaster=auto -o ControlPersist=60s`: ansible-core 2.16.20 `lib/ansible/plugins/connection/ssh.py:78-80`). Kolla ships no `ansible.cfg` for deployments (the only one in the tree is the CI template `tests/templates/ansible.cfg.j2`), so `pipelining` stays off and each invocation still makes several round trips (tmp dir, transfer, exec, cleanup) | `pipelining = True` (requires no `requiretty`; `doc/source/user/ansible-tuning.rst:8-18`). On large fleets, a longer persistence such as `ssh_args = -C -o ControlMaster=auto -o ControlPersist=30m` |
| Certificate distribution | `service-cert-copy` (when `kolla_copy_ca_into_containers`, `no` by default: `group_vars/all.yml:928`) | every service config dir | C×S | per service | `copy` per service dir (`roles/service-cert-copy/tasks/main.yml:2-12`) | Only enable when needed |

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
- `F_eff` = min(forks, batch size, what the deploy host CPU and SSH can sustain); the first two bounds are in the code
  (ansible-core 2.16.20 `lib/ansible/executor/task_queue_manager.py:320-321`), the third is [NOT AVAILABLE].
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

| Computes (C) | Compute task results, full `reconfigure` (per-compute count n/a) | Compute remote invocations, full `reconfigure` (per-compute count n/a) | `kolla_set_configs --check` execs on computes (10·C) | Compute task results, `-t nova` (per-compute count n/a) | Invocations, `-t nova` (27·C) | Waves per task at F=20 | Waves per task at F=50 | Waves per task at F=100 | Image pulls for a full image update (10·C) | Delegated fact `setup` calls with `--limit <1 host>` (*N* − 1 = C + 7 with 8 non-compute hosts, localhost included) |
|---|---|---|---|---|---|---|---|---|---|---|
| 10 | n/a | n/a | 100 | n/a | 270 | 1 | 1 | 1 | 100 | 17 |
| 50 | n/a | n/a | 500 | n/a | 1,350 | 3 | 1 | 1 | 500 | 57 |
| 100 | n/a | n/a | 1,000 | n/a | 2,700 | 5 | 2 | 1 | 1,000 | 107 |
| 200 | n/a | n/a | 2,000 | n/a | 5,400 | 10 | 4 | 2 | 2,000 | 207 |
| 500 | n/a | n/a | 5,000 | n/a | 13,500 | 25 | 10 | 5 | 5,000 | 507 |

Reading the table:

- **No-change `-t nova reconfigure`, C=500, F=50.** Each compute runs a chain of 27 remote invocations. With 10
  waves per task, the compute-side critical path is ≈ **270 × t_inv** plus deploy-host templating
  (500 × nova.conf renders) and the constant delegated steps. Nothing restarts, and yet the run still costs
  ~13,500 remote invocations and 1,500 `docker exec` config checks (3 per compute).
- **The same run after a global change** (e.g. `enable_barbican`) adds a handler phase: 500 × (nova_ssh + nova_libvirt
  + nova_compute) = **1,500 container restarts**, all in the same flush unless batched. The common containers
  (fluentd, cron, kolla_toolbox) are not touched by `-t nova`; they restart at the next run of the `common` play
  (`site.yml:88-103`) when their own files change (for `enable_barbican`, fluentd and cron:
  `roles/common/tasks/config.yml:140-203, :205-270`).
- **Image updates multiply data volume.** A tag change downloads 10 images per compute: 5,000 image pulls at C=500.
  Registry egress ≈ C × Σ(size of the new layers); image sizes are [NOT AVAILABLE]
  ([Q8](../troubleshooting/open-questions.md#q8) in [Findings](../reference/findings.md)). With the default
  `forks`/serial, this traffic is concurrent across up to `forks` hosts.
- **Fact gathering with `--limit`.** Gathering the 507 other hosts serially from one host costs ≈507 × t_setup before
  any real work. Fact caching removes it.

### 4.3 What is constant, per batch, or per host

| Constant (D) | Per batch (with `serial`) | Per controller | Per compute | Per container | Conditional |
|---|---|---|---|---|---|
| Keystone registration, DB create/grant, DB-sync containers, cell create/update, `map_cell0`, haproxy frontend rendering (per `loadbalancer` host) | all `run_once` steps above, compute registration wait (up to 20 × 10 s of sleep), `discover_hosts` | API configs, MariaDB/RabbitMQ rolling restarts (per DB/MQ node) | facts, `group_by`, common (when its play runs), config-host, nova-cell/OVS/neutron config, OVS and nova-cell post-config | `compare_container` exec, image pull, restart/recreate | handlers (drift), image download (new image), `update_cell` (URL change), Docker restart (`daemon.json` change) |

---

## 5. Why a small change becomes a large workload

Two independent multipliers apply. Still holds in 2024.1.

1. **Work multiplier (always).** Every run that includes the `compute` group executes the full per-host chain on
   every compute, even with no change ([§2](#2-work-per-compute-host-read-from-the-task-files)): config re-rendering and
   comparison, container config checks, common role (in untagged runs), sysctl and modules, OVS post-config,
   discovery. **Kolla has no "only if changed" short-circuit at play level.**
2. **Restart multiplier (when inputs are global).** Global inputs are rendered into every compute's files ([Component
   dependencies §5](../components/dependencies.md#5-compute-node-dependency-summary)). Loop-notify widens a single
   drifted container to the whole role on that host: when one item of a looped task changes, the task result is
   changed and every non-skipped item's handler is notified (ansible-core 2.16.20
   `lib/ansible/executor/task_executor.py:126-130`, `lib/ansible/plugins/strategy/__init__.py:648-671`; [Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)). Without `serial`,
   all restarts land in one handler flush.

---

## 6. Scaling at 3, 10 and 30 computes, read from the code

The scenarios of [§2](#2-work-per-compute-host-read-from-the-task-files) at 3, 10 and 30 computes, for an inventory with
3 controllers, 2 network nodes, 1 storage node, 1 monitoring node and localhost (the shape of
`inventory/multinode:3-33` with more computes). Counts on computes come from
[§2](#2-work-per-compute-host-read-from-the-task-files) [CODE]. Cells marked n/a are [NOT AVAILABLE]: the sources give
neither task-result totals, nor the non-compute part of the fleet counts, nor durations.

| Scenario | Computes | forks | Task results (fleet) | per compute | `compare_container` calls on computes | Restarts/recreates | nova-cell play duration | Total duration |
|---|---|---|---|---|---|---|---|---|
| `deploy` (first time) | 3 | 20 | n/a | n/a | 30 (no check exec) | n/a | n/a | n/a |
| `deploy` (first time) | 10 | 20 | n/a | n/a | 100 (no check exec) | n/a | n/a | n/a |
| `deploy` (first time) | 30 | 20 | n/a | n/a | 300 (no check exec) | n/a | n/a | n/a |
| `-t nova reconfigure` (no change) | 3 | 20 | n/a | n/a | 9 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change) | 10 | 20 | n/a | n/a | 30 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change) | 30 | 20 | n/a | n/a | 90 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change), forks 5 | 30 | 5 | n/a | n/a | 90 | 0 | n/a | n/a |
| `-t nova reconfigure` (no change), forks 50 | 30 | 50 | n/a | n/a | 90 | 0 | n/a | n/a |
| `-t nova reconfigure` with a nova-compute-only override | 30 | 20 | n/a | n/a | 90 | **90** (30 × nova_compute + nova_libvirt + nova_ssh) | n/a | n/a |
| `-t nova reconfigure --limit compute001` (no change) | 30 | 20 | n/a | n/a | 3 | 0 | n/a | n/a |

What the code shows:

1. **Per-compute work is constant and fleet work is linear.**
   - Every compute runs the same task files for the same services
     ([§2](#2-work-per-compute-host-read-from-the-task-files)), so the per-compute counts do not depend on C and the
     compute part of every fleet count grows by the per-compute count. The per-compute task-result counts for a deploy
     and a `-t nova` run are [NOT AVAILABLE].
   - The number of `compare_container` calls grows by 10 per compute for a deploy and 3 per compute for `-t nova`.
     A call runs `docker exec kolla_set_configs --check` only when the container exists and no other attribute
     differs; it then also compares the container's systemd unit file (`module_utils/kolla_container_worker.py:58-65`,
     `module_utils/kolla_docker_worker.py:146-181`). On a first-time deploy every container is missing, so no check
     exec runs; a no-change run does one exec per call [CODE]. With Podman the same steps go through
     `module_utils/kolla_podman_worker.py`; this page counts the Docker path only.
   - forks changes none of these counts: it only bounds how many hosts run a task at once
     (ansible-core 2.16.20 `lib/ansible/executor/task_queue_manager.py:320-321`) [CODE].
2. **The compute-wide plays grow with C.**
   - The plays that run on every compute are common, iscsi (with Cinder LVM), nova-cell, openvswitch and neutron
     (`site.yml:88-103, :439-452, :611-624, :671-693`; `nova.yml:125-147`; `compute` is in the `common`, `iscsid` and
     `openvswitch` groups: `inventory/multinode:49-53, :105-108, :305-308`) [CODE]. Still holds in 2024.1. The share
     of run time they take as C grows is [NOT AVAILABLE].
3. **forks and the deploy host's CPU.**
   - Whether, and at which forks value, the deploy host's CPU becomes the bottleneck is [NOT AVAILABLE]
     ([Q7](../troubleshooting/open-questions.md#q7) in [Findings](../reference/findings.md)).
   - What runs on the deploy host is in the code [CODE]: one worker process per queued host/task, up to forks
     (ansible-core 2.16.20 `lib/ansible/executor/task_queue_manager.py:320-321`,
     `lib/ansible/plugins/strategy/__init__.py:387-419`), module packaging (AnsiballZ) for every invocation
     (ansible-core 2.16.20 `lib/ansible/plugins/action/__init__.py:225`, `:300`), templating of `nova.conf.j2`
     (`ansible/action_plugins/merge_configs.py:149-165`) and the per-host `group_by` loop (`site.yml:20-74`).
   - Whether forks overlap SSH and remote-execution latency in production, and up to which point, is
     [NOT AVAILABLE].
   - Size the deploy host (cores) together with forks.
4. **A small change restarts the fleet in one step** [CODE]. With one nova-compute-only override on 30 computes,
   loop-notify ([Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code))
   notifies `nova_compute`, `nova_libvirt` and `nova_ssh` on every compute: 90 container restarts. Without `serial` all
   30 computes are in one batch (`nova.yml:140`, `serial` defaults to "0" and `tools/kolla-ansible:296` sets
   `ANSIBLE_SERIAL=0`; ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:181-190, :286-288, :300-301`),
   so the restarts run at one handler flush (`roles/nova-cell/tasks/deploy.yml:16-17`), on at most `forks` hosts at a
   time (ansible-core 2.16.20 `lib/ansible/plugins/strategy/__init__.py:387-419, :952-963`). How close together they
   land in time is [NOT AVAILABLE].
5. **`--limit` bounds the restarts, but fact gathering stays O(inventory)** [CODE].
   - With `--limit compute001` on the 30-compute inventory (38 hosts, localhost included), compute001 runs
     **38 `setup` calls in sequence**: its own (`gather-facts.yml:19-25`), plus one delegated call for each of the
     37 other inventory hosts (`gather-facts.yml:34-62`: with one limited host, the slice `groups['all'][0::1]` is the
     whole inventory, minus the limited host itself, `:47`, `:59`). The delegated loop runs its items one after another
     (ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:288`, `:336`). Its duration is [NOT AVAILABLE].
   - The delegated `discover_hosts`/`list_cells` work runs on the first conductor, control01
     (`roles/nova-cell/tasks/wait_discover_computes.yml:42-43`, `discover_computes.yml:21`).
   - With SSH, multiply the delegated count by the real per-host `setup` time; at 500 computes it is ≈508 sequential
     fact gatherings before any work starts.

---

## 7. Influence of the main variables

| Variable | Effect | Guidance |
|---|---|---|
| **Ansible forks** | Divides the number of waves per task (⌈H/F⌉). Bounded by deploy-host CPU (templating, AnsiballZ build per invocation) and memory (one worker process per queued host/task, up to forks) | Raise until deploy-host CPU saturates; where that happens is [NOT AVAILABLE] ([§6](#6-scaling-at-3-10-and-30-computes-read-from-the-code)). Size the deploy host for templating |
| **Serial (`kolla_serial`)** | Bounds simultaneous *restarts* per play, but **adds** time: every batch re-runs `run_once` steps and the compute registration wait, and each batch waits for the slowest host | Use it for restart safety on changes with drift, not for no-change runs. Prefer `genconfig` + `deploy-containers --limit` batches |
| **`max_fail_percentage`** (new in 2024.1) | Set on every play, 100 unless `kolla_max_fail_percentage` or a per-service variable is set (`etc/kolla/globals.yml:27-31`, commented out); compared with the failures of the current batch only ([§1](#1-how-ansible-core-216-spends-time-in-kolla-ansible)) | Leave at 100 for no-change runs; a lower value makes a batch stop the play when too many of its hosts fail |
| **Task delegation** | `delegate_to` steps serialise on one host (conductor[0], neutron-server[0], rabbitmq[0]) | That host's health gates the whole run |
| **SSH overhead** | Each remote invocation pays several SSH round trips (tmp dir, transfer, exec, cleanup). The connection itself is reused: ansible-core defaults to `ControlMaster=auto` with `ControlPersist=60s` (ansible-core 2.16.20 `lib/ansible/plugins/connection/ssh.py:78-80`), so a new handshake happens only after a host has been idle for 60 s | `pipelining = True` (requires no `requiretty` in sudoers) is the main lever. On large fleets, a longer `ControlPersist` (keep `-C -o ControlMaster=auto` in `ssh_args`) and a short `ControlPath` |
| **Docker image size** | Pull time and disk I/O per host | Local registry, pre-pull, avoid unnecessary tag churn |
| **Network bandwidth** | Concurrent pulls from up to `forks` hosts | Cap with `--forks` during `pull`; registry caching |
| **Disk I/O** | Image extraction, container creation, `/etc/kolla` writes | SSD for `/var/lib/docker` |
| **Container startup time** | Handlers start the container through its systemd unit and wait until the unit is running, polled every 5 s (`module_utils/kolla_docker_worker.py:365-390`, `module_utils/kolla_systemd_worker.py:97-113, :205-216`), not for service readiness, except explicit waits (haproxy, OVS DB, MariaDB WSREP, RabbitMQ) | – |
| **Handler execution** | Runs at the flush in parallel; `docker_graceful_timeout` (60 s by default, `group_vars/all.yml:139, :151`) bounds stop time | Batch to bound the blast radius |
| **Parallel vs sequential** | Hosts run in parallel within a task; items and tasks run sequentially per host; plays are sequential | Reduce items (disable unused services), use tags to skip plays, use `--limit` to skip hosts |

---

## 8. Bottlenecks and optimisation opportunities (ranked)

1. **Avoid running compute-wide plays when you do not need them.**
   - Use `-t nova-api` for API-only changes (no computes: the nova-cell play is not tagged `nova-api`,
     `nova.yml:110-114, :135-139`).
   - Use `--limit` for host-scoped changes.
   - Use `--skip-tags haproxy` when frontends are not changing (it skips the whole loadbalancer play:
     `site.yml:105-118`).
2. **Separate config from apply.** `genconfig` once, then `deploy-containers --limit <batch>`. With `-t nova`, the
   apply step on a compute runs only `setup` and the `check-containers.yml` loop of nova-cell
   (4 invocations instead of 27 for `-t nova reconfigure`, [§2](#2-work-per-compute-host-read-from-the-task-files)), and
   runs no bootstrap or Keystone steps [CODE: `roles/nova-cell/tasks/deploy-containers.yml:2`,
   `roles/nova/tasks/deploy-containers.yml:2`, `nova.yml:53-55, :89-91`]. In 2024.1, `genconfig` also runs the common
   play's `ensure_image` of fluentd, which pulls that image when it is absent (`roles/common/tasks/config.yml:42-51`).
3. **Fact caching + setup filter.** This removes the O(N) serial delegated gathering under `--limit` and speeds the
   first play. All options are documented in `doc/source/user/ansible-tuning.rst`.
4. **SSH pipelining** cuts the per-invocation constant that multiplies 27–31 invocations per compute in a `-t nova`
   run (the count for a full run is [NOT AVAILABLE]). A longer `ControlPersist` than the 60 s default avoids
   repeated handshakes on large fleets.
5. **Size forks to the deploy host.** Templating of large Jinja templates (`nova.conf.j2`, `neutron.conf.j2`) happens
   on the deploy host, per compute.
6. **Pre-pull images** (`kolla-ansible pull`) before upgrade windows, from a nearby registry.
7. **Minimise global drift.**
   - Batch `enable_*` changes.
   - Avoid touching RabbitMQ/memcached membership casually.
   - Keep compute-relevant overrides in `nova/nova-compute.conf` (or, new in 2024.1, `nova/<host>/nova-compute.conf`
     for one host: `roles/nova-cell/tasks/config.yml:80`) rather than the global `nova.conf`.
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
