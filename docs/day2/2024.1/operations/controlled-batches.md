---
title: Write config first, apply in controlled batches
description: "In 2024.1, write the config with genconfig and apply it batch by batch with deploy-containers --limit, or roll a reconfigure with ANSIBLE_SERIAL."
tags: [nova, genconfig, deploy-containers, reconfigure, serial, limit, loop-notify, kolla-set-configs, max-fail-percentage]
remember:
  - "<code>genconfig</code> (zero restarts), a review of the diff, then <code>deploy-containers --limit &lt;batch&gt;</code>: each batch restarts only its hosts. <code>genconfig -t nova-cell</code> also renders the conductor and console config on controllers: give them a batch too. <span class=\"ev ev-code\">CODE</span>"
  - "Until all batches are applied, any untagged, <code>-t nova</code> or <code>-t nova-cell</code> run, a container restart or a reboot applies the pending drift: keep the window short. <span class=\"ev ev-code\">CODE</span>"
  - "Drift confined to <code>config.json</code>'s <code>command</code> or <code>permissions</code> is never detected; it takes effect only at the next restart for another reason. <span class=\"ev ev-code\">CODE</span>"
  - "<code>ANSIBLE_SERIAL</code> reaches only <code>reconfigure</code> and <code>upgrade</code>. mariadb and rabbitmq restart with a fixed <code>serial: \"33%\"</code>, etcd has no <code>serial</code> any more and stages its restarts in its handlers, and cyborg ignores it. <span class=\"ev ev-code\">CODE</span>"
  - "Every play now has <code>max_fail_percentage</code>, default 100, which never stops a play early: set <code>kolla_max_fail_percentage</code> (or <code>&lt;service&gt;_max_fail_percentage</code>) lower to stop a rolling run when a batch has failures. <span class=\"ev ev-code\">CODE</span>"
impact: [writes-config, restarts-on-drift]
scenarios:
  - title: "Half-way through the batches"
    situation: "On a cloud with 40 computes, you ran <code>kolla-ansible -t nova-cell genconfig</code> on Monday and applied the first two batches with <code>deploy-containers --limit</code>. On Wednesday, before the remaining batches, a colleague wants to run <code>kolla-ansible -t nova reconfigure</code> for an unrelated nova fix, and another wants to reboot the remaining computes for a kernel update."
    ask: "What would you do?"
    choices:
      - text: "Let the colleague run <code>-t nova reconfigure</code> now: it only applies the nova fix."
        verdict: "avoid"
        why: "Between <code>genconfig</code> and the last batch, any other Kolla run that reaches the nova-cell check on those hosts applies the pending drift in files listed in <code>config_files</code>: an untagged run, <code>-t nova</code> or <code>-t nova-cell</code> <span class=\"ev ev-code\">CODE</span>. The remaining computes would restart outside your batches."
      - text: "Reboot the remaining computes first and run the batches afterwards."
        verdict: "risky"
        why: "A container that starts again for any reason also picks up the new config, because <code>COPY_ALWAYS</code> copies the files and rewrites <code>/run_command</code> at container start <span class=\"ev ev-code\">CODE</span>. The new config would be applied by the reboots, not by your controlled batches."
      - text: "Finish the remaining <code>deploy-containers --limit</code> batches first, including a batch for the controllers, and only then allow other runs."
        verdict: "best"
        why: "The page says to keep the window between writing and applying short, and to apply controllers with their own <code>--limit</code> batch: <code>genconfig -t nova-cell</code> also renders the conductor and console config on controllers, or the drift stays pending there <span class=\"ev ev-code\">CODE</span>."
    see: "2-separate-write-config-from-apply-recommended-pattern"
  - title: "A rolling reconfigure that should stop on the first bad batch"
    situation: "You plan <code>ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure</code> on 40 computes. Your change manager asks that the run stop as soon as a compute of a batch fails, instead of carrying on with the next batches."
    ask: "What would you do?"
    choices:
      - text: "Nothing more: 2024.1 sets <code>max_fail_percentage</code> on every play, so the run already stops on failures."
        verdict: "avoid"
        why: "The default is 100, which never stops a play early: the failed hosts drop out and the next batches run. Only a batch in which every host failed ends the run <span class=\"ev ev-code\">CODE</span>."
      - text: "Set <code>kolla_max_fail_percentage: 0</code> in <code>globals.yml</code> (or <code>nova_cell_max_fail_percentage</code> for the nova-cell plays) for this run."
        verdict: "best"
        why: "The plays read <code>&lt;service&gt;_max_fail_percentage</code>, then <code>kolla_max_fail_percentage</code>, then 100. With 0, one failed host of the current batch exceeds the limit, the play breaks and the run stops before the next batch <span class=\"ev ev-code\">CODE</span>."
      - text: "Use <code>ANSIBLE_SERIAL=1</code> so that a failure can only ever touch one compute."
        verdict: "risky"
        why: "Batches bound how many hosts a play touches at once, but with the default 100 the run still carries on after a failed host, and <code>run_once</code> tasks repeat once per batch, e.g. <code>nova_api_bootstrap</code> once per controller and compute discovery once per batch with computes <span class=\"ev ev-code\">CODE</span>."
    see: "13-stop-a-rolling-run-on-failures-max_fail_percentage"
quiz:
  - q: "What does <code>deploy-containers</code> run?"
    options: ["Everything a <code>deploy</code> runs", "Only <code>check-containers.yml</code> and the handlers it notifies"]
    answer: 1
    explain: "It restarts each container with drift written by <code>genconfig</code> and, by loop-notify, the other containers of that role on the same host; no bootstrap and no Keystone registration run."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "With <code>genconfig</code>, then <code>deploy-containers --limit &lt;batch&gt;</code>, which hosts restart?"
    options: ["Only the hosts of the batch", "Every compute at once"]
    answer: 0
    explain: "Each batch restarts only its hosts, and only the containers whose check finds drift."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "A newly rendered <code>optional</code> file is not yet in the container. What does <code>kolla_set_configs --check</code> do?"
    options: ["It exits 1 (drift): the restart copies the new file", "It exits 2 and the task fails"]
    answer: 0
    explain: "A source without its destination counts as drift for <code>optional</code> files too; this still holds in 2024.1, where <code>set_configs.py</code> is unchanged."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "With <code>ANSIBLE_SERIAL=10</code> and the default settings, one compute of the first batch fails. What happens?"
    options: ["The run stops before the second batch", "The failed compute drops out and the next batches run"]
    answer: 1
    explain: "<code>max_fail_percentage</code> defaults to 100, which never stops a play early; only a batch in which every host failed ends the run."
    see: "13-stop-a-rolling-run-on-failures-max_fail_percentage"
  - q: "Which play is no longer batched by <code>ANSIBLE_SERIAL</code> in 2024.1, while it was in 2023.1?"
    options: ["etcd", "nova-cell"]
    answer: 0
    explain: "The etcd play has no <code>serial</code> key any more; its handlers restart the non-leaders in groups, then the leader."
    see: "12-rolling-reconfigure-with-ansible_serial"
---

# Write config first, apply in controlled batches

How to write the configuration first and apply it batch by batch, with Nova as the example. `genconfig`, a review of the
diff, then `deploy-containers --limit <batch>` is the only built-in way to separate "write the config" from "apply it"
([Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)). The page
also covers a rolling `reconfigure` with `ANSIBLE_SERIAL`, and how to make it stop on failures with
`max_fail_percentage`, new on every play in 2024.1.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **Compute changes in controlled batches:** `-t nova-cell genconfig`, then `deploy-containers --limit` batch by batch
>   ([§1.1](#11-compute-changes-in-controlled-batches-recommended-pattern)). Rolling runs with `ANSIBLE_SERIAL`:
>   [§1.2](#12-rolling-reconfigure-with-ansible_serial).
> - **Stop a rolling run on failures:** lower `kolla_max_fail_percentage` (or `<service>_max_fail_percentage`); the
>   default 100 never stops a play early ([§1.3](#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
> - **What changed since 2023.1:** etcd is no longer batched by `ANSIBLE_SERIAL`, outward RabbitMQ is gone, and every
>   play carries `max_fail_percentage`. The pattern itself, the drift check and its blind spots still hold.

## 1. Commands

### 1.1 Compute changes in controlled batches (recommended pattern)

```bash
# 1. write the config everywhere, restart nothing
kolla-ansible -i multinode -t nova-cell genconfig
# 2. review: diff /etc/kolla/nova-compute/nova.conf on a sample of hosts
# 3. apply batch by batch (only check-containers + handlers run)
kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[0:9]'
kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[10:19]'
```

- `genconfig` runs the playbooks with `kolla_action=config` (`tools/kolla-ansible:557-560`), and `deploy-containers`
  with `kolla_action=deploy-containers` (`tools/kolla-ansible:499-502`). Neither sets `kolla_serial`.
- `deploy-containers` runs only `check-containers.yml` and the handlers it notifies [CODE
  `roles/nova-cell/tasks/deploy-containers.yml:2`]. These restart each container with drift written by `genconfig`
  and, by loop-notify, the other containers of that role on the same host: the nova-cell check is one looped task whose
  `notify` names `Restart {{ item.key }} container` (`roles/nova-cell/tasks/check-containers.yml:2-22`), and
  ansible-core 2.16.20 saves the notifications of every item of a looped task once the task as a whole is changed
  (`lib/ansible/plugins/strategy/__init__.py:648-661`) [CODE; [Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)].

  Drift is found by `compare_container`: the container is missing, its parameters differ, `kolla_set_configs --check`
  reports a change, or the systemd unit text differs (`module_utils/kolla_container_worker.py:58-65`). Through
  `kolla_set_configs --check` it sees only drift in the files listed in `config.json`'s `config_files` (existence,
  content, perm, owner) [CODE kolla `docker/base/set_configs.py:165-198`, `docker/base/set_configs.py:220-242`,
  `docker/base/set_configs.py:556-559`]. It does not see changes to `config.json`'s own `command`/`permissions` (e.g.
  memcached: empty `config_files`, `roles/memcached/templates/memcached.json.j2:1-4`), and no later
  `deploy`/`reconfigure` restarts for those either, because the `config.json` template task is then unchanged; they
  take effect at the next restart for another reason. **Still holds in 2024.1:** kolla's `set_configs.py` is
  byte-identical to 2023.1 ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

  A newly rendered `optional` file whose destination is not yet in the container (e.g. nova-compute's `release`) counts
  as drift: `--check` exits 1 and the restart copies the new file (kolla `docker/base/set_configs.py:165-171`,
  `roles/nova-cell/templates/nova-compute.json.j2:52-58`). Exit 1 means "changed" for both container engines
  (Docker `module_utils/kolla_docker_worker.py:164-172`, Podman `module_utils/kolla_podman_worker.py:442-449`).
- Each batch restarts only its hosts. No bootstrap containers and no Keystone registration run: the two bootstrap
  plays of `nova.yml` act only for `deploy` and `reconfigure` (`nova.yml:53-55`, `nova.yml:89-91`), and the role
  runs `deploy-containers.yml` instead of `deploy.yml` (`roles/nova-cell/tasks/main.yml:2`). The service includes of the
  `loadbalancer` play are skipped too
  (`site.yml:324-326`).
- **Caveat:** `genconfig -t nova-cell` also renders the conductor and console config on controllers, because the
  nova-cell play targets `nova-conductor`, `nova-novncproxy`, `nova-serialproxy` and `nova-spicehtml5proxy` as well
  as `compute` (`nova.yml:125-134`). Include them in a batch too, or the drift stays pending there.
- **New in 2024.1, first run after the code update:** nova-cell now writes a `hostnqn` file for nova-compute
  (`roles/nova-cell/tasks/config.yml:203-216`) and lists it in `config_files` without `optional`
  (`roles/nova-cell/templates/nova-compute.json.j2:59-63`). On a compute whose nova_compute container was created by
  2023.1 code, that file is not in the container yet, so the first 2024.1 check reports drift there even if you
  changed nothing else.
- The `compute[0:9]` slice syntax is standard Ansible host-pattern slicing.

### 1.2 Rolling reconfigure with `ANSIBLE_SERIAL`

```bash
ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure
```

- `ANSIBLE_SERIAL` reaches the plays only for `reconfigure` and `upgrade`, as `kolla_serial`
  (`tools/kolla-ansible:522`, `tools/kolla-ansible:531`); it defaults to 0, i.e. no batching
  (`tools/kolla-ansible:296`). Those `-e kolla_serial=…` options are added after your own `-e` options
  (`tools/kolla-ansible:366-368`), so for these two actions use the environment variable. Plays that set
  `serial: '{{ kolla_serial|default("0") }}'` run in batches of 10 hosts: gather-facts, common, the `loadbalancer`
  play, all nova plays and almost every service play (`gather-facts.yml:11`, `gather-facts.yml:40`, `site.yml:95`,
  `site.yml:110`, `nova.yml:140`).
- **Not batched by it:**
  - **mariadb and rabbitmq**, separate playbooks (imported at `site.yml:400` and `site.yml:468`) whose role plays have
    no
    `serial` (`mariadb.yml:3-16`, `rabbitmq.yml:3-28`). Their handlers only add hosts to restart groups, and the
    restart plays use a fixed `serial: "33%"` (`mariadb.yml:24`, `mariadb.yml:42`, `rabbitmq.yml:36`). ansible-core
    rounds the percentage down with a minimum of one host (`lib/ansible/utils/helpers.py:30-32`): with three nodes,
    one node per batch. **Changed in 2024.1:** outward RabbitMQ and its plays are gone; `rabbitmq.yml` has a single
    restart play.
  - **etcd (changed in 2024.1).** In 2023.1 its play used `kolla_serial`; in 2024.1 it has no `serial` key
    (`site.yml:470-481`). Its handlers stage the restarts instead: look up the leader, restart the non-leaders (outside
    `upgrade` and `config`, looping over the four values of `groups.etcd.index(host) % 4`), then the leader, whose
    handler is defined last (`roles/etcd/handlers/main.yml:9-17`, `roles/etcd/handlers/main.yml:40-55`,
    `roles/etcd/handlers/main.yml:57-65`). On `upgrade` a separate handler loops over `groups.etcd` for the non-leaders
    (`roles/etcd/handlers/main.yml:29-36`). Each restart waits for the client port and for `etcdctl endpoint health`
    (`roles/etcd/tasks/restart_services.yml:16-41`). [NOT AVAILABLE] How ansible-core orders, across hosts, the files
    included by one looped handler, so whether the `% 4` groups really restart one after another ([Execution flow
    §7](../concepts/deployment-execution-flow.md#7-dependencies-introduced-by-handlers)).
  - **cyborg**, whose play reads `serial` instead of `kolla_serial` and so ignores `ANSIBLE_SERIAL` (`site.yml:876`).
    **Still holds in 2024.1.**
  - the helper plays (group-by, prechecks), which change nothing (`site.yml:7-75`, `site.yml:77-86`).
- A `run_once` task runs once per batch of its own play: the linear strategy sends it to the first host of the current
  batch only (`lib/ansible/plugins/strategy/linear.py:181`, `lib/ansible/plugins/strategy/linear.py:207-209`). For
  `-t nova`, the API DB sync (`nova_api_bootstrap`, `roles/nova/tasks/bootstrap_service.yml:21`), `map_cell0`
  (`roles/nova/tasks/map_cell0.yml:63-64`) and the Keystone registration
  (`roles/service-ks-register/tasks/main.yml:126`) are `run_once` in plays that target only controller groups
  (nova-api, nova-scheduler, nova-super-conductor: `nova.yml:29-39`, `nova.yml:103-115`), so they repeat only if those
  groups are larger than the batch. The cell DB sync (`nova_cell_bootstrap`) is not `run_once`: it is gated on the
  first nova-conductor and runs once at any serial value (`roles/nova-cell/tasks/bootstrap_service.yml:21`). Compute
  discovery runs on the first compute of each nova-cell batch, so it repeats once per batch that contains computes
  (`roles/nova-cell/tasks/deploy.yml:19-37`, `roles/nova-cell/tasks/wait_discover_computes.yml:87-90`). With
  `kolla_serial=1` and the three `multinode` controllers (`ansible/inventory/multinode:3-7`, `nova-api` and
  `nova-conductor` are children of `nova`, `ansible/inventory/multinode:227-231`): `nova_api_bootstrap` ×3,
  `nova_cell_bootstrap` ×1, discovery once per compute
  [CODE, [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)].
- Batches apply per play: the whole fleet passes the nova-cell play before the next play starts. ansible-core 2.16.20
  loops over the plays (`lib/ansible/executor/playbook_executor.py:126`) and, inside each play, over its batches,
  restricting the inventory to one batch per run (`lib/ansible/executor/playbook_executor.py:181-190`) [CODE;
  [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order)].

### 1.3 Stop a rolling run on failures (`max_fail_percentage`)

```bash
# stop the run as soon as one host of a batch fails
ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure -e kolla_max_fail_percentage=0
```

New in 2024.1 [CODE]:

- Every play of `site.yml`, `gather-facts.yml`, `mariadb.yml` and `rabbitmq.yml`, and the nova plays except the cell
  bootstrap and the two online-migration plays, set `max_fail_percentage` from `<service>_max_fail_percentage`, then
  `kolla_max_fail_percentage`, then 100 (e.g. `site.yml:96-99`, `gather-facts.yml:7-10`, `mariadb.yml:25-28`,
  `nova.yml:141-144`). The nova-cell plays read `nova_cell_max_fail_percentage`, the nova API plays
  `nova_max_fail_percentage` (`nova.yml:40-43`). The cell bootstrap play keeps `any_errors_fatal: true` instead
  (`nova.yml:78-79`). `kolla_max_fail_percentage` is unset by default, and `globals.yml` says that 100 is equivalent
  to not setting it (`etc/kolla/globals.yml:27-31`).
- ansible-core 2.16.20 compares the hosts failed **in the current batch** with the batch size: the play breaks when
  `failed / batch_size` is greater than the percentage (`lib/ansible/plugins/strategy/linear.py:336-348`), and the
  failed-host list is cleared at the start of each batch (`lib/ansible/executor/task_queue_manager.py:332-338`). With
  100 that never happens. A broken play stops the whole run (`lib/ansible/executor/playbook_executor.py:196-198`,
  `lib/ansible/executor/playbook_executor.py:219-220`). The value may be a string such as `"0"` or `"10%"`: it is
  converted to a number (`lib/ansible/playbook/base.py:449-454`).
- Whatever the value, a batch in which every host failed ends the run
  (`lib/ansible/executor/playbook_executor.py:204-209`). Hosts that failed in an earlier batch or play are marked
  failed again at the start of each later run of the task queue, so they drop out of the rest of the run
  (`lib/ansible/executor/task_queue_manager.py:332-334`).
- So, with the default 100 and `ANSIBLE_SERIAL=10`, a failed compute drops out and the next batches carry on. With
  `0`, the first failed host of a batch stops the run before the next batch; hosts of the current batch that had not
  failed are marked failed too and stop where they are (`lib/ansible/plugins/strategy/linear.py:341-346`), so check
  their state before you resume.
- The restart plays of mariadb and rabbitmq read the same variables (`mariadb.yml:25-28`, `rabbitmq.yml:37-40`): with
  one node per batch, any value below 100 stops the run when that node fails.

## 2. Separate "write config" from "apply" (recommended pattern)

[CODE]

1. `kolla-ansible -t nova genconfig` writes the new `nova.conf` on all hosts. **Zero restarts**: every container restart
   handler has `when: kolla_action != "config"` (e.g. `roles/nova-cell/handlers/main.yml:89-90`,
   `roles/nova-cell/handlers/main.yml:114-115`, `roles/nova-cell/handlers/main.yml:167-168`). The handlers without
   that condition are waits, checks, `group_by` steps and bootstrap steps chained from other handlers, handlers gated
   on `kolla_action == "upgrade"` (e.g. `roles/etcd/handlers/main.yml:29-36`), plus swift's no-op `debug` handler
   (`roles/swift/handlers/main.yml:2-4`). The etcd handlers that restart outside `upgrade` carry the condition too
   (`roles/etcd/handlers/main.yml:40-65`), and so do the mariadb and rabbitmq handlers that fill the restart groups
   (`roles/mariadb/handlers/main.yml:56-73`, `roles/rabbitmq/handlers/main.yml:2-6`). **Still holds in 2024.1**, from a
   scan of every `roles/*/handlers/main.yml`.

   An untagged `genconfig` also runs the common play, which in 2024.1 makes sure the fluentd image is present, pulling
   it if absent (`roles/common/tasks/config.yml:42-51`): no container restarts, but an image pull is possible.
2. `kolla-ansible -t nova deploy-containers --limit compute001` restarts only compute001's nova containers. Drift is
   detected by `kolla_set_configs --check` inside `compare_container` (`module_utils/kolla_container_worker.py:20`,
   `module_utils/kolla_container_worker.py:58-65`). On compute001, with the default `nova_compute_virt_type: "kvm"`
   (`group_vars/all.yml:1127`, `group_vars/all.yml:827`), its tasks make 4
   remote module invocations (`setup` and 3 `compare_container`: nova-libvirt, nova-ssh, nova-compute) plus the
   delegated fact loop (`gather-facts.yml:19-25`, `gather-facts.yml:49-61`;
   `roles/nova-cell/tasks/check-containers.yml:2-22`). **Still holds in 2024.1:** roles have no `meta` dependency and
   common runs only in its own play, tagged `common` (`site.yml:88-103`) ([Compute scaling
   §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)). No
   bootstrap, no Keystone registration and no haproxy work run (`roles/nova-cell/tasks/deploy-containers.yml:2`,
   `nova.yml:53-55`, `site.yml:324-326`).
3. Repeat per batch. Controllers (API, scheduler, conductor) are applied with their own `--limit` batch.

Caveats:

- **HAProxy frontends are not applied by this pattern.** `genconfig` also re-renders
  `/etc/kolla/haproxy/services.d/` (the loadbalancer block runs for `config`, `site.yml:324-326`), while every
  loadbalancer
  handler is skipped under `config` (`roles/loadbalancer/handlers/main.yml:17`), and `deploy-containers` runs no
  haproxy work. A frontend change written this way reaches HAProxy only through `-t haproxy reconfigure` or a run
  without tags [CODE]; copy `services.d` before `genconfig` if you want to diff it.
- Between steps 1 and 3, **any other Kolla run that reaches the nova-cell check on those hosts applies the pending
  drift in files listed in `config_files`**: an untagged run, `-t nova` or `-t nova-cell` (the tags of the nova-cell
  play, `nova.yml:135-139`). Unrelated tags do not do it through common: common runs only for an untagged run or
  `-t common` (`site.yml:100-101`).
- Drift confined to `config.json`'s `command` or `permissions` (e.g. memcached's `-m`/`-c`, whose `config_files` is
  empty, `roles/memcached/templates/memcached.json.j2:1-4`) is never detected: `kolla_set_configs --check` compares
  only `config_files` (kolla `docker/base/set_configs.py:556-559`, [Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)), and the template
  task is already unchanged. No later Kolla run restarts the container for it, step 2 included. It takes effect only at
  the next restart for another reason.
- Containers that start again for any other reason (a container engine restart, a reboot) also pick up the new
  config, because `COPY_ALWAYS` copies the files and rewrites `/run_command` at container start (kolla
  `docker/base/set_configs.py:302-316`, `docker/base/set_configs.py:535-541`). Keep the window short.

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
- [R1](../risk/risk-register.md#r1) — the risk whose precautions name this pattern and `ANSIBLE_SERIAL`
