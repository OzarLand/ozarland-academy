---
title: Write config first, apply in controlled batches
description: Write the configuration with genconfig, then apply it batch by batch with deploy-containers --limit, or roll a reconfigure with ANSIBLE_SERIAL.
tags: [nova, genconfig, deploy-containers, reconfigure, serial, limit, loop-notify, kolla-set-configs]
remember:
  - "<code>genconfig</code> (zero restarts), a review of the diff, then <code>deploy-containers --limit &lt;batch&gt;</code>: each batch restarts only its hosts. <span class=\"ev ev-code\">CODE</span>"
  - "Until all batches are applied, any other Kolla run that reaches those hosts (even <code>-t chrony</code>), a Docker restart or a reboot applies the pending drift: keep the window short. <span class=\"ev ev-code\">CODE</span>"
  - "<code>genconfig -t nova-cell</code> also renders the conductor and console config on controllers: include them in a batch too, or the drift stays pending there."
  - "Drift confined to <code>config.json</code>'s <code>command</code> or <code>permissions</code> is never detected; it takes effect only at the next restart for another reason. <span class=\"ev ev-code\">CODE</span>"
  - "With <code>ANSIBLE_SERIAL</code>, mariadb, rabbitmq and outward rabbitmq are not batched, and cyborg ignores it."
impact: [writes-config, restarts-on-drift]
scenarios:
  - title: "Half-way through the batches"
    situation: "On a cloud with 40 computes, you ran <code>kolla-ansible -t nova-cell genconfig</code> on Monday and applied the first two batches with <code>deploy-containers --limit</code>. On Wednesday, before the remaining batches, a colleague wants to run <code>kolla-ansible -t nova reconfigure</code> for an unrelated nova fix, and another wants to reboot the remaining computes for a kernel update."
    ask: "What would you do?"
    choices:
      - text: "Let the colleague run <code>-t nova reconfigure</code> now: it only applies the nova fix."
        verdict: "avoid"
        why: "Between <code>genconfig</code> and the last batch, any other Kolla run that reaches those hosts applies the pending drift in files listed in <code>config_files</code> <span class=\"ev ev-code\">CODE</span>. That includes an unrelated <code>-t chrony</code> run that touches common (it checks the common containers, not the nova ones); <code>-t nova</code> reaches the computes. The remaining computes would restart outside your batches."
      - text: "Reboot the remaining computes first and run the batches afterwards."
        verdict: "risky"
        why: "Hosts restarted by Docker or reboot also pick up the new config, because <code>COPY_ALWAYS</code> copies the files and rewrites <code>/run_command</code> at container start <span class=\"ev ev-code\">CODE</span>. The new config would be applied by the reboots, not by your controlled batches."
      - text: "Finish the remaining <code>deploy-containers --limit</code> batches first, including a batch for the controllers, and only then allow other runs."
        verdict: "best"
        why: "The page says to keep the window between writing and applying short, and to apply controllers with their own <code>--limit</code> batch: <code>genconfig -t nova-cell</code> also renders the conductor and console config on controllers, or the drift stays pending there."
    see: "2-separate-write-config-from-apply-recommended-pattern"
quiz:
  - q: "What does <code>deploy-containers</code> run?"
    options: ["Everything a <code>deploy</code> runs", "Only <code>check-containers.yml</code> and the handlers it notifies"]
    answer: 1
    explain: "It restarts each container with drift written by <code>genconfig</code> and, by loop-notify, the other containers of that role on the same host."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "With <code>genconfig</code>, then <code>deploy-containers --limit &lt;batch&gt;</code>, which hosts restart?"
    options: ["Only the hosts of the batch", "Every compute at once"]
    answer: 0
    explain: "Each batch restarts only its hosts; no bootstrap containers and no Keystone registration run."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
  - q: "A newly rendered <code>optional</code> file is not yet in the container. What does <code>kolla_set_configs --check</code> do?"
    options: ["It exits 1 (drift): the restart copies the new file", "It exits 2 and the task fails"]
    answer: 1
    explain: "Unless an entry listed before it differs too: then it exits 1 and the restart copies the new file."
    see: "11-compute-changes-in-controlled-batches-recommended-pattern"
---

# Write config first, apply in controlled batches

How to write the configuration first and apply it batch by batch, with Nova as the example. `genconfig`, a review of the
diff, then `deploy-containers --limit <batch>` is the only built-in way to separate "write the config" from "apply it"
([Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)). The page
also covers a rolling `reconfigure` with `ANSIBLE_SERIAL`.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **Compute changes in controlled batches:** `-t nova-cell genconfig`, then `deploy-containers --limit` batch by batch
>   ([§1.1](#11-compute-changes-in-controlled-batches-recommended-pattern)). Rolling runs with `ANSIBLE_SERIAL`:
>   [§1.2](#12-rolling-reconfigure-with-ansible_serial).

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

- `deploy-containers` runs only `check-containers.yml` and the handlers it notifies. These restart each container with
  drift written by `genconfig` and, by loop-notify, the other containers of that role on the same host [CODE
  `roles/nova-cell/tasks/deploy-containers.yml:2`; [Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)].

  Through `kolla_set_configs --check` it sees only drift in the files listed in `config.json`'s `config_files` (content,
  owner, perm) [CODE kolla `docker/base/set_configs.py:160-191,407-410`]. It does not see changes to `config.json`'s own
  `command`/`permissions` (e.g. memcached: empty `config_files`), and no later `deploy`/`reconfigure` restarts for those
  either, because the `config.json` template task is then unchanged; they take effect at the next restart for another
  reason.

  A newly rendered `optional` file whose destination is not yet in the container (e.g. nova-compute's `release`) makes
  `--check` exit 2 and the task fail, unless an entry listed before it (here `nova.conf`, if it changed too) differs:
  then it exits 1 and the restart copies the new file ([Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
- Each batch restarts only its hosts. No bootstrap containers, no Keystone registration and no haproxy play run.
- **Caveat:** `genconfig -t nova-cell` also renders the conductor and console config on controllers. Include them
  in a batch too, or the drift stays pending there.
- The `compute[0:9]` slice syntax is standard Ansible host-pattern slicing.

### 1.2 Rolling reconfigure with `ANSIBLE_SERIAL`

```bash
ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure
```

- Plays that set `serial: kolla_serial` run in batches of 10 hosts: gather-facts, the haproxy play, all nova plays
  and almost every service play. Not batched: mariadb, rabbitmq and outward rabbitmq (no `serial`; their rolling
  logic is in the handlers); cyborg, which uses `serial` instead of `kolla_serial` and so ignores `ANSIBLE_SERIAL`
  (bug, `site.yml:1028`); and the helper plays (group-by, CentOS check, prechecks), which change nothing.
- A `run_once` task runs once per batch of its own play. For `-t nova`, the API DB sync (`nova_api_bootstrap`,
  `map_cell0`) and the Keystone registration are `run_once` in plays that target only controller groups (nova-api,
  nova-scheduler, nova-super-conductor), so they repeat only if those groups are larger than the batch. The cell DB sync
  (`nova_cell_bootstrap`) is not `run_once`: it is gated on the first nova-conductor and runs once at any serial value.
  Compute discovery runs on the first compute of each nova-cell batch, so it repeats once per batch that contains
  computes [CODE, [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code) and
  `roles/nova-cell/tasks/bootstrap_service.yml:21`: with `kolla_serial=1` and the three `multinode` controllers,
  `nova_api_bootstrap` ×3, `nova_cell_bootstrap` ×1, discovery once per compute].
- Batches apply per play: the whole fleet passes the nova-cell play before the next play starts [CODE ansible 2.9.27
  `lib/ansible/executor/playbook_executor.py:161-169`].

## 2. Separate "write config" from "apply" (recommended pattern)

[CODE]

1. `kolla-ansible -t nova genconfig` writes the new `nova.conf` on all hosts. **Zero restarts**: every container restart
   handler has `when: kolla_action != "config"` (e.g. `roles/nova-cell/handlers/main.yml:84-85, :107-108, :139-140`).
   The only unguarded restart handlers are the deprecated nova-hyperv Windows-service ones, which `-t nova` does not
   select ([Pre-execution checklist](pre-execution-checklist.md)).
2. `kolla-ansible -t nova deploy-containers --limit compute001` restarts only compute001's nova containers. Drift is
   detected by `kolla_set_configs --check` inside `compare_container`. On compute001 its tasks make 7 remote module
   invocations (`setup` and 6 `compare_container`) plus the delegated fact loop ([Compute scaling
   §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files)), with no
   bootstrap, no Keystone registration and no haproxy play (`roles/nova-cell/tasks/deploy-containers.yml:2`,
   `nova.yml:49-51`, `site.yml:390-392`).
3. Repeat per batch. Controllers (API, scheduler, conductor) are applied with their own `--limit` batch.

Caveats:

- Between steps 1 and 3, **any other Kolla run that reaches those hosts applies the pending drift in files listed in
  `config_files`**. That includes an unrelated `-t chrony` run that touches common: the nova containers are not
  checked by it, but the common ones are.
- Drift confined to `config.json`'s `command` or `permissions` (e.g. memcached's `-m`/`-c`, whose `config_files` is
  empty) is never detected: `kolla_set_configs --check` compares only `config_files` (kolla
  `docker/base/set_configs.py:407-410`, [Kolla images
  §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)), and the template
  task is already unchanged. No later Kolla run restarts the container for it, step 2 included. It takes effect only at
  the next restart for another reason.
- Hosts restarted by Docker or reboot also pick up the new config, because `COPY_ALWAYS` copies the files and rewrites
  `/run_command` at container start (kolla `docker/base/set_configs.py:319-324,391-393`). Keep the window short.

## Related

- [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) — the action
  matrix: what `genconfig` and `deploy-containers` run and skip
- [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) —
  batching with `serial`: a batch runs the complete play before the next batch starts
- [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code) — what `run_once` tasks repeat when `serial` is set
- [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) — what
  `kolla_set_configs --check` compares and what it never compares
- [Predict and inspect a run](predict-a-run.md) — the `kolla_set_configs --check` command, to see what will restart
  after `genconfig`
- [Reconfigure Nova](reconfigure-nova.md) — what `-t nova reconfigure` runs and restarts
- [R1](../risk/risk-register.md#r1) — the risk whose precautions name this pattern and `ANSIBLE_SERIAL`
