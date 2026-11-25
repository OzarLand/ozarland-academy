---
title: Write config first, apply in controlled batches
description: "In 2025.1, write config with genconfig, apply it in batches with deploy-containers --limit, or roll a deploy with kolla_serial; reconfigure cannot be batched."
tags: [nova, genconfig, deploy-containers, reconfigure, serial, limit, kolla-set-configs, max-fail-percentage]
remember:
  - "<code>genconfig</code> (no restart for Nova), a review of the diff, then <code>deploy-containers --limit &lt;batch&gt;</code>: each batch restarts only the changed containers of its hosts. <code>genconfig -t nova-cell</code> also renders the conductor and console config on controllers: give them a batch too. <span class=\"ev ev-code\">CODE</span>"
  - "Until all batches are applied, any untagged, <code>-t nova</code> or <code>-t nova-cell</code> run, a container restart or a reboot applies the pending drift: keep the window short. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: <code>reconfigure</code> and <code>upgrade</code> always run with <code>kolla_serial=0</code>, and <code>ANSIBLE_SERIAL</code> is gone. For a rolling run, use <code>deploy -e kolla_serial=N</code>, which runs the same tasks as <code>reconfigure</code>. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: a change of <code>command</code> in <code>config.json</code> is now detected and applied by <code>deploy-containers</code>; a change of <code>permissions</code> still is not. <span class=\"ev ev-code\">CODE</span>"
  - "Every play has <code>max_fail_percentage</code>, default 100, which never stops a play early: set <code>kolla_max_fail_percentage</code> (or <code>&lt;service&gt;_max_fail_percentage</code>) lower to stop a rolling run when a batch has failures. <span class=\"ev ev-code\">CODE</span>"
impact: [writes-config, restarts-on-drift]
scenarios:
  - title: "Half-way through the batches"
    situation: "On a cloud with 40 computes, you ran <code>kolla-ansible genconfig -t nova-cell</code> on Monday and applied the first two batches with <code>deploy-containers --limit</code>. On Wednesday, before the remaining batches, a colleague wants to run <code>kolla-ansible reconfigure -t nova</code> for an unrelated nova fix, and another wants to reboot the remaining computes for a kernel update."
    ask: "What would you do?"
    choices:
      - text: "Let the colleague run <code>reconfigure -t nova</code> now: it only applies the nova fix."
        verdict: "avoid"
        why: "Between <code>genconfig</code> and the last batch, any other Kolla run that reaches the nova-cell check on those hosts applies the pending drift: an untagged run, <code>-t nova</code> or <code>-t nova-cell</code> <span class=\"ev ev-code\">CODE</span>. The remaining computes would restart outside your batches, all at once, since <code>reconfigure</code> cannot be batched in 2025.1."
      - text: "Reboot the remaining computes first and run the batches afterwards."
        verdict: "risky"
        why: "A container that starts again for any reason also picks up the new config, because <code>COPY_ALWAYS</code> copies the files and rewrites <code>/run_command</code> at container start <span class=\"ev ev-code\">CODE</span>. The new config would be applied by the reboots, not by your controlled batches."
      - text: "Finish the remaining <code>deploy-containers --limit</code> batches first, including a batch for the controllers, and only then allow other runs."
        verdict: "best"
        why: "The page says to keep the window between writing and applying short, and to apply controllers with their own <code>--limit</code> batch: <code>genconfig -t nova-cell</code> also renders the conductor and console config on controllers, or the drift stays pending there <span class=\"ev ev-code\">CODE</span>."
    see: "2-separate-write-config-from-apply-recommended-pattern"
  - title: "A rolling change that should stop on the first bad batch"
    situation: "You plan to roll a Nova change over 40 computes, 10 at a time, and your notes from 2024.1 say <code>ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure</code>. Your change manager also asks that the run stop as soon as a compute of a batch fails."
    ask: "What would you do?"
    choices:
      - text: "Run the 2024.1 command unchanged: <code>ANSIBLE_SERIAL=10 kolla-ansible reconfigure -t nova</code>."
        verdict: "avoid"
        why: "The 2025.1 CLI does not read <code>ANSIBLE_SERIAL</code>; <code>reconfigure</code> always adds <code>kolla_serial=0</code>, so every compute is handled in one batch, and with the default <code>max_fail_percentage</code> of 100 the run does not stop on a failed host <span class=\"ev ev-code\">CODE</span>."
      - text: "Run <code>kolla-ansible deploy -t nova -e kolla_serial=10 -e kolla_max_fail_percentage=0</code>."
        verdict: "best"
        why: "<code>deploy</code> runs the same tasks as <code>reconfigure</code> and adds no <code>kolla_serial</code>, so your value batches the plays. With <code>kolla_max_fail_percentage</code> 0, one failed host of the current batch breaks the play and the run stops before the next batch <span class=\"ev ev-code\">CODE</span>."
      - text: "Run <code>kolla-ansible reconfigure -t nova -e kolla_serial=10</code>."
        verdict: "risky"
        why: "The command's own <code>-e kolla_serial=0</code> is passed after yours and the later value wins, so the plays run with 0: no batching <span class=\"ev ev-code\">CODE</span>. A lab run has not confirmed it yet."
    see: "12-rolling-runs-with-kolla_serial-not-with-reconfigure"
quiz:
  - q: "What does <code>deploy-containers</code> run?"
    options: ["Everything a <code>deploy</code> runs", "Only <code>check-containers.yml</code> and the handlers it notifies"]
    answer: 1
    explain: "It restarts each container whose check finds drift, and in 2025.1 only that container: the loop-notify of 2024.1 is gone. No bootstrap and no Keystone registration run."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "With <code>genconfig</code>, then <code>deploy-containers --limit &lt;batch&gt;</code>, which hosts restart?"
    options: ["Only the hosts of the batch", "Every compute at once"]
    answer: 0
    explain: "Each batch restarts only its hosts, and only the containers whose check finds drift."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "In 2025.1, does <code>kolla-ansible reconfigure -e kolla_serial=10</code> reconfigure 10 hosts at a time?"
    options: ["Yes", "No: the command passes its own <code>kolla_serial=0</code> after yours"]
    answer: 1
    explain: "<code>reconfigure</code> and <code>upgrade</code> add <code>kolla_serial=0</code> after the user's <code>-e</code>, and the later value wins. Use <code>deploy -e kolla_serial=10</code>, which runs the same tasks."
    see: "12-rolling-runs-with-kolla_serial-not-with-reconfigure"
  - q: "With <code>-e kolla_serial=10</code> and the default settings, one compute of the first batch fails. What happens?"
    options: ["The run stops before the second batch", "The failed compute drops out and the next batches run"]
    answer: 1
    explain: "<code>max_fail_percentage</code> defaults to 100, which never stops a play early; only a batch in which every host failed ends the run."
    see: "13-stop-a-rolling-run-on-failures-max_fail_percentage"
  - q: "You change <code>memcached_max_memory</code>, run <code>genconfig</code>, then <code>deploy-containers --limit</code> on the memcached hosts. What happens in 2025.1?"
    options: ["Nothing: a <code>command</code> change in <code>config.json</code> is never detected", "memcached restarts with the new size: <code>--check</code> now compares the command"]
    answer: 1
    explain: "<code>kolla_set_configs --check</code> now fails with <code>ConfigFileCommandDiffers</code> when the <code>command</code> of <code>config.json</code> differs from the one the container started with. In 2024.1 this change was never detected."
    see: "2-separate-write-config-from-apply-recommended-pattern"
---

# Write config first, apply in controlled batches

How to write the configuration first and apply it batch by batch, with Nova as the example. `genconfig`, a review of the
diff, then `deploy-containers --limit <batch>` is the only built-in way to separate "write the config" from "apply it"
([Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)). The page
also covers a rolling run with `-e kolla_serial`, which in 2025.1 works only with `deploy` and the other commands that
do not set `kolla_serial`, and how to make it stop on failures with `max_fail_percentage`.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **Compute changes in controlled batches:** `genconfig -t nova-cell`, then `deploy-containers --limit` batch by batch
>   ([§1.1](#11-compute-changes-in-controlled-batches-recommended-pattern)).
> - **Changed in 2025.1: a rolling `reconfigure` is no longer possible.** `ANSIBLE_SERIAL` is gone, and `reconfigure`
>   and `upgrade` always pass `kolla_serial=0` after your `-e`. Use `deploy -e kolla_serial=N`, which runs the same
>   tasks ([§1.2](#12-rolling-runs-with-kolla_serial-not-with-reconfigure)).
> - **Stop a rolling run on failures:** lower `kolla_max_fail_percentage` (or `<service>_max_fail_percentage`); the
>   default 100 never stops a play early ([§1.3](#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
> - **What else changed since 2024.1:** `deploy-containers` restarts only the containers that changed (no more
>   loop-notify); a change of `command` in `config.json` is now detected; `genconfig` restarts nothing for Nova and no
>   longer pulls the fluentd image. The pattern itself still holds.

## 1. Commands

### 1.1 Compute changes in controlled batches (recommended pattern)

```bash
# 1. write the config everywhere, restart nothing
kolla-ansible genconfig -i multinode -t nova-cell
# 2. review: diff /etc/kolla/nova-compute/nova.conf on a sample of hosts
# 3. apply batch by batch (only check-containers + handlers run)
kolla-ansible deploy-containers -i multinode -t nova-cell --limit 'compute[0:9]'
kolla-ansible deploy-containers -i multinode -t nova-cell --limit 'compute[10:19]'
```

The action now comes first (`kolla-ansible <action> <options>`); see [Conventions](../start/conventions.md).

- `genconfig` runs the playbooks with `kolla_action=config` (`kolla_ansible/cli/commands.py:113-125`), and
  `deploy-containers` with `kolla_action=deploy-containers` (`kolla_ansible/cli/commands.py:245-256`). Neither sets
  `kolla_serial`.
- `deploy-containers` runs only `check-containers.yml` and the handlers it notifies [CODE
  `roles/nova-cell/tasks/deploy-containers.yml:2`]. **Changed in 2025.1:** these restart only the containers with
  drift. The nova-cell `check-containers.yml` imports the shared `service-check-containers` role
  (`roles/nova-cell/tasks/check-containers.yml:2-3`), which compares every container in one loop and then notifies a
  list built from the changed results only (`roles/service-check-containers/tasks/main.yml:4-29, :34-41`) [CODE;
  [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)]. In 2024.1, one changed container restarted
  every nova-cell container of the host.

  Drift is found by `compare_container`: the container is missing, its parameters differ, `kolla_set_configs --check`
  reports a change, or the systemd unit text differs (`module_utils/kolla_container_worker.py:58-65`). Through
  `kolla_set_configs --check` it sees drift in the files listed in `config.json`'s `config_files` (existence,
  content, perm, owner) [CODE kolla `docker/base/set_configs.py:178-211, :233-255`] and, **new in 2025.1**, two more
  cases (kolla `docker/base/set_configs.py:580-586, :589-636, :655-657`):
  - the `command` of `config.json` differs from the one the container started with (`ConfigFileCommandDiffers`). So a
    memcached setting change, which lives in that `command` (`roles/memcached/templates/memcached.json.j2:1-4`), is now
    applied by `deploy-containers`;
  - a file that an earlier `config.json` listed is no longer listed (`StateMismatch`).

  A change confined to the `permissions` list of `config.json` is still not seen: the check path does not run
  `handle_permissions` (`set_configs.py:347, :655-657`); it takes effect at the next restart for another reason
  ([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

  A newly rendered `optional` file whose destination is not yet in the container (e.g. nova-compute's `release`) counts
  as drift: `--check` exits 1 and the restart copies the new file (kolla `docker/base/set_configs.py:180-182, :237-252`,
  `roles/nova-cell/templates/nova-compute.json.j2:59-64`). Exit 1 means "changed" for both container engines
  (Docker `module_utils/kolla_docker_worker.py:164-172`, Podman `module_utils/kolla_podman_worker.py:540-547`).
- Each batch restarts only its hosts. No bootstrap containers and no Keystone registration run: the two bootstrap
  plays of `nova.yml` act only for `deploy` and `reconfigure` (`nova.yml:53-55`, `nova.yml:89-91`), and the role
  runs `deploy-containers.yml` instead of `deploy.yml` (`roles/nova-cell/tasks/main.yml:2`). The new libvirt version
  check is part of `deploy.yml`, so it does not run either (`roles/nova-cell/tasks/deploy.yml:5`). The service includes
  of the `loadbalancer` play and its final check are skipped too (`site.yml:325-327`).
- **Caveat:** `genconfig -t nova-cell` also renders the conductor and console config on controllers, because the
  nova-cell play targets `nova-conductor`, `nova-novncproxy`, `nova-serialproxy` and `nova-spicehtml5proxy` as well
  as `compute` (`nova.yml:125-134`). Include them in a batch too, or the drift stays pending there.
- **New in 2025.1, first run after the code update:** whatever you changed, the first check after the upgrade from
  2024.1 can report drift on every container, because the systemd unit now carries `PartOf=kolla.target` and, with
  Docker on hosts outside the Red Hat family, the default `ulimits` changed ([Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). Run that
  first apply as its own controlled batch sequence, or after the upgrade itself, not together with a config change.
- The `compute[0:9]` slice syntax is standard Ansible host-pattern slicing.

### 1.2 Rolling runs with `kolla_serial` (not with `reconfigure`)

```bash
# batches of 10 hosts per play; deploy runs the same tasks as reconfigure
kolla-ansible deploy -i multinode -t nova -e kolla_serial=10
```

- **Changed in 2025.1:** `ANSIBLE_SERIAL` is no longer read. `ANSIBLE_SERIAL = 0` is a constant of the CLI
  (`kolla_ansible/cli/commands.py:20-22`), and `reconfigure` and `upgrade` always add `kolla_serial=0`
  (`kolla_ansible/cli/commands.py:136, :278`). That value comes after your own `-e` options
  (`kolla_ansible/ansible.py:261-266`), and ansible-core keeps the last value of a repeated extra var
  (`lib/ansible/utils/vars.py:94-105, :198-224`), so `reconfigure -e kolla_serial=10` runs with 0 [CODE; a lab run has
  not confirmed it]. `deploy`, `deploy-containers`, `pull`, `genconfig`, `stop` and `check` set no `kolla_serial`, so
  your `-e kolla_serial=10` reaches their plays.
- **`deploy` instead of `reconfigure`.** For a given tag both run the same tasks: every role's `reconfigure.yml` but
  bifrost's imports or includes `deploy.yml` ([Repository architecture
  §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)), the nova bootstrap plays act for both
  (`nova.yml:53-55`, `nova.yml:89-91`), and no task under `ansible/` tests `kolla_action == "deploy"` or `==
  "reconfigure"` on its own (a search of the tree finds the two values only together, in lists) [CODE].
- Plays that set `serial: '{{ kolla_serial|default("0") }}'` run in batches of 10 hosts: gather-facts, common, the
  `loadbalancer` play, all nova plays and almost every service play (`gather-facts.yml:11`, `gather-facts.yml:40`,
  `site.yml:95`, `site.yml:110`, `nova.yml:140`).
- **Not batched by it:**
  - **mariadb and rabbitmq**, separate playbooks (imported at `site.yml:415` and `site.yml:483`) whose role plays have
    no `serial` (`mariadb.yml:3-16`, `rabbitmq.yml:3-28`). Their handlers only add hosts to restart groups, and the
    restart plays use a fixed `serial: "33%"` (`mariadb.yml:24`, `mariadb.yml:42`, `rabbitmq.yml:36`). ansible-core
    rounds the percentage down with a minimum of one host (`lib/ansible/utils/helpers.py:28-30`): with three nodes,
    one node per batch.
  - **etcd**, whose play has no `serial` key (`site.yml:485-496`). Its handlers stage the restarts instead: look up the
    leader, restart the non-leaders (outside `upgrade`, looping over the four values of `groups.etcd.index(host) % 4`),
    then the leader, whose handler is defined after them (`roles/etcd/handlers/main.yml:9-15`,
    `roles/etcd/handlers/main.yml:38-52`, `roles/etcd/handlers/main.yml:54-61`). On `upgrade` a separate handler loops
    over `groups.etcd` for the non-leaders (`roles/etcd/handlers/main.yml:27-34`). Each restart waits for the client
    port and for `etcdctl endpoint health` (`roles/etcd/tasks/restart_services.yml:16-41`). [NOT AVAILABLE] How
    ansible-core orders, across hosts, the files included by one looped handler, so whether the `% 4` groups really
    restart one after another ([Execution flow §7](../concepts/deployment-execution-flow.md#7-dependencies-introduced-by-handlers)).
  - **cyborg**, whose play reads `serial` instead of `kolla_serial` and so ignores it (`site.yml:874`). **Still holds
    in 2025.1.**
  - the helper plays (group-by, prechecks), which change nothing (`site.yml:7-75`, `site.yml:77-86`).
- A `run_once` task runs once per batch of its own play: the linear strategy sends it to the first host of the current
  batch only (`lib/ansible/plugins/strategy/linear.py:178`, `lib/ansible/plugins/strategy/linear.py:205-206`). For
  `-t nova`, the API DB sync (`nova_api_bootstrap`, `roles/nova/tasks/bootstrap_service.yml:21`), `map_cell0`
  (`roles/nova/tasks/map_cell0.yml:63-64`) and the Keystone registration
  (`roles/service-ks-register/tasks/main.yml:129`) are `run_once` in plays that target only controller groups
  (nova-api, nova-scheduler, nova-super-conductor: `nova.yml:29-39`, `nova.yml:103-115`), so they repeat only if those
  groups are larger than the batch. The cell DB sync (`nova_cell_bootstrap`) is not `run_once`: it is gated on the
  first nova-conductor and runs once at any serial value (`roles/nova-cell/tasks/bootstrap_service.yml:21`). Compute
  discovery runs on the first compute of each nova-cell batch, so it repeats once per batch that contains computes
  (`roles/nova-cell/tasks/deploy.yml:21-39`, `roles/nova-cell/tasks/wait_discover_computes.yml:87-90`). The new
  libvirt version check is `run_once` too, so it runs once per nova-cell batch
  (`roles/nova-cell/tasks/version-check.yml:20-21`). With `kolla_serial=1` and the three `multinode` controllers
  (`inventory/multinode:3-6`; `nova-api` and `nova-conductor` are children of `nova`, `inventory/multinode:226-230`):
  `nova_api_bootstrap` ×3, `nova_cell_bootstrap` ×1, discovery once per compute [CODE, [Tags
  §2.5](../risk/tags.md#25-run_once-with-serial-code)].
- Batches apply per play: the whole fleet passes the nova-cell play before the next play starts. ansible-core 2.18.20
  loops over the plays (`lib/ansible/executor/playbook_executor.py:124`) and, inside each play, over its batches,
  restricting the inventory to one batch per run (`lib/ansible/executor/playbook_executor.py:183-191`) [CODE;
  [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order)].

### 1.3 Stop a rolling run on failures (`max_fail_percentage`)

```bash
# stop the run as soon as one host of a batch fails
kolla-ansible deploy -i multinode -t nova -e kolla_serial=10 -e kolla_max_fail_percentage=0
```

[CODE]:

- Every play of `site.yml`, `gather-facts.yml`, `mariadb.yml` and `rabbitmq.yml`, and the nova plays except the cell
  bootstrap and the two online-migration plays, set `max_fail_percentage` from `<service>_max_fail_percentage`, then
  `kolla_max_fail_percentage`, then 100 (e.g. `site.yml:96-99`, `gather-facts.yml:7-10`, `mariadb.yml:25-28`,
  `nova.yml:141-144`). The nova-cell plays read `nova_cell_max_fail_percentage`, the nova API plays
  `nova_max_fail_percentage` (`nova.yml:40-43`). The cell bootstrap play keeps `any_errors_fatal: true` instead
  (`nova.yml:78-79`). `kolla_max_fail_percentage` is unset by default, and `globals.yml` says that 100 is equivalent
  to not setting it (`etc/kolla/globals.yml:27-31`).
- ansible-core 2.18.20 compares the hosts failed **in the current batch** with the batch size: the play breaks when
  `failed / batch_size` is greater than the percentage (`lib/ansible/plugins/strategy/linear.py:336-347`), and the
  failed-host list is cleared at the start of each batch (`lib/ansible/executor/task_queue_manager.py:334`). With
  100 that never happens. A broken play stops the whole run (`lib/ansible/executor/playbook_executor.py:194-196`,
  `lib/ansible/executor/playbook_executor.py:214-215`). The value may be a string such as `"0"` or `"10%"`: it is
  converted to a number (`lib/ansible/playbook/base.py:455-460`).
- Whatever the value, a batch in which every host failed ends the run
  (`lib/ansible/executor/playbook_executor.py:199-204`). Hosts that failed in an earlier batch or play are marked
  failed again at the start of each later run of the task queue (`lib/ansible/executor/task_queue_manager.py:323-329`).
- So, with the default 100 and `kolla_serial=10`, a failed compute drops out and the next batches carry on. With
  `0`, the first failed host of a batch stops the run before the next batch; hosts of the current batch that had not
  failed are marked failed too and stop where they are (`lib/ansible/plugins/strategy/linear.py:339-344`), so check
  their state before you resume.
- The restart plays of mariadb and rabbitmq read the same variables (`mariadb.yml:25-28`, `rabbitmq.yml:37-40`): with
  one node per batch, any value below 100 stops the run when that node fails.
- The same applies to the new `check` command: a container that is missing, stopped or unhealthy fails its host
  (`roles/service-check/tasks/main.yml:12-40`), so with a value below 100 a `check` run can stop early.

## 2. Separate "write config" from "apply" (recommended pattern)

[CODE]

1. `kolla-ansible genconfig -t nova` writes the new `nova.conf` on all hosts. **No restart.** **Changed in 2025.1:**
   the reason is new. The nova and nova-cell config steps notify no handler any more (in 2025.1 only Placement's WSGI
   file and Cinder's Huawei XML files still notify from a config step,
   [Conventions](../start/conventions.md#operation-impact-classes), row `writes-config`), and `genconfig` does not
   run the container check, so nothing notifies the restart handlers. Most handlers therefore no longer carry the
   `kolla_action != "config"` guard of 2024.1 (`roles/nova-cell/handlers/main.yml:70-159` has none on its restart
   handlers; the guard is left only on `Reload libvirtd`, `:135-141`). An untagged `genconfig` also runs the common
   play, which **no longer** pulls the fluentd image (2025.1 `roles/common/tasks/config.yml` has no `ensure_image`
   task).
2. `kolla-ansible deploy-containers -t nova --limit compute001` restarts only the nova containers of compute001 that
   changed. Drift is detected by `kolla_set_configs --check` inside `compare_container`
   (`module_utils/kolla_container_worker.py:58-65`). On compute001, with the default `nova_compute_virt_type: "kvm"`
   (`group_vars/all.yml:1253`, `group_vars/all.yml:945`), its tasks make 4 remote module invocations (`setup` and 3
   `compare_container`: nova-libvirt, nova-ssh, nova-compute) plus the delegated fact loop and the one notify task
   (`gather-facts.yml:19-25`, `gather-facts.yml:49-61`; `roles/service-check-containers/tasks/main.yml:4-41`). Roles
   have no `meta` dependency and common runs only in its own play, tagged `common` (`site.yml:88-103`) ([Compute
   scaling §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)). No
   bootstrap, no Keystone registration and no haproxy work run (`roles/nova-cell/tasks/deploy-containers.yml:2`,
   `nova.yml:53-55`, `site.yml:325-327`).
3. Repeat per batch. Controllers (API, metadata, scheduler, conductor) are applied with their own `--limit` batch.

Caveats:

- **HAProxy frontends are not applied by this pattern.** `genconfig` also re-renders
  `/etc/kolla/haproxy/services.d/` (the loadbalancer block runs for `config`, `site.yml:325-327`), but the
  loadbalancer play's check step is skipped for `config` (`site.yml:319-324`), and `deploy-containers` runs no
  haproxy work. A frontend change written this way reaches HAProxy only through `reconfigure -t haproxy` (or
  `loadbalancer`) or a run without tags [CODE]; in 2025.1 a `-t nova` run does not apply it either ([Tags
  §2.2](../risk/tags.md#22-handlers-ignore-tags-code)). Copy `services.d` before `genconfig` if you want to diff it.
- Between steps 1 and 3, **any other Kolla run that reaches the nova-cell check on those hosts applies the pending
  drift**: an untagged run, `-t nova` or `-t nova-cell` (the tags of the nova-cell play, `nova.yml:135-139`).
  Unrelated tags do not do it through common: common runs only for an untagged run or `-t common`
  (`site.yml:100-101`).
- A change confined to the `permissions` list of `config.json` is never detected ([§1.1](#11-compute-changes-in-controlled-batches-recommended-pattern)).
  No Kolla run restarts the container for it, step 2 included. It takes effect only at the next restart for another
  reason.
- Containers that start again for any other reason (a container engine restart, a reboot) also pick up the new
  config, because `COPY_ALWAYS` copies the files and rewrites `/run_command` at container start (kolla
  `docker/base/set_configs.py:315-330`, `docker/base/set_configs.py:559-565`). Keep the window short.

## Related

- [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) — the action
  matrix: what `genconfig` and `deploy-containers` run and skip
- [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) —
  batching with `serial`, and `max_fail_percentage`: a batch runs the complete play before the next batch starts
- [Execution flow §7](../concepts/deployment-execution-flow.md#7-dependencies-introduced-by-handlers) — the staged
  etcd handlers
- [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code) — what `run_once` tasks repeat when `serial` is set
- [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) — what
  `kolla_set_configs --check` compares and what it never compares
- [Predict and inspect a run](predict-a-run.md) — the `kolla_set_configs --check` command, to see what will restart
  after `genconfig`
- [Reconfigure Nova](reconfigure-nova.md) — what `-t nova reconfigure` runs and restarts
- [R1](../risk/risk-register.md#r1) — the risk whose precautions name this pattern
