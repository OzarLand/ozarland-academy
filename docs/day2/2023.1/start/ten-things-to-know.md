---
title: Ten things to know before a production run
description: Ten things to know before running Kolla-Ansible 2023.1 on production, most of them with the section that gives the evidence.
tags: [reconfigure, deploy, loop-notify, serial, tags, limit, images, kolla-set-configs, genconfig, handlers, risk]
remember:
  - "<code>reconfigure</code> is <code>deploy</code> for 57 of the 59 roles that have a <code>reconfigure.yml</code>; the only lightweight path is <code>genconfig</code> followed by <code>deploy-containers</code>."
  - "Config is applied by a full stop/start, never a reload, and the stop timeout is 60 s."
  - "One changed container restarts all containers of its role on that host."
  - "Without batching, handlers restart a service on every host of the play at once; <code>deploy</code> ignores <code>ANSIBLE_SERIAL</code> and needs <code>-e kolla_serial=N</code>."
  - "<code>deploy</code> never pulls an image that is already present: rebuilt images under the same tag need <code>pull</code>."
quiz:
  - q: "What is the only lightweight path to apply config?"
    options: ["<code>reconfigure</code>", "<code>deploy</code> with a service tag", "<code>genconfig</code> followed by <code>deploy-containers</code>"]
    answer: 2
    explain: "<code>reconfigure</code> is <code>deploy</code> for 57 of the 59 roles that have a <code>reconfigure.yml</code>. The only lightweight path is <code>genconfig</code> followed by <code>deploy-containers</code>."
  - q: "Without batching, how do handlers restart a service?"
    options: ["On every host of the play at once", "One host at a time"]
    answer: 0
    explain: "Without batching, handlers restart a service on every host of the play at once. Batching is <code>ANSIBLE_SERIAL</code> for <code>reconfigure</code>/<code>upgrade</code> and <code>-e kolla_serial=N</code> for <code>deploy</code>, which ignores <code>ANSIBLE_SERIAL</code>."
  - q: "In 2023.1, what applies fluentd, cron and kolla_toolbox changes?"
    options: ["Any service tag, which also runs <code>common</code>", "<code>-t common</code> or a run without tags", "<code>-t chrony</code>"]
    answer: 1
    explain: "<code>common</code> is its own play, tagged <code>common</code>, so these changes need <code>-t common</code> or a run without tags; a service tag leaves them pending. The Ussuri workaround <code>-t chrony</code> no longer exists."
---

# Ten things to know before a production run

Ten things to know before running Kolla-Ansible 2023.1 on production. Most items link to the section that gives the
evidence.

1. **`reconfigure` is `deploy`** for 57 of the 59 roles that have a `reconfigure.yml` (swift and bifrost are the
   exceptions). It re-runs Keystone registration, DB creation and the DB-sync bootstrap containers for most services,
   Neutron's included in 2023.1. The only lightweight path is `genconfig` followed by `deploy-containers` ([Execution
   flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)).
2. **Config is applied by a full stop/start, never a reload, and the stop timeout is 60 s.** Containers run under
   systemd units whose stop is `docker stop -t <docker_graceful_timeout>`, 60 s by default; a service still running
   then is killed ([R24](../risk/risk-register.md#r24), [Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)). The only signal
   Kolla sends to a running container is a `SIGHUP` to `nova_scheduler`, which refreshes its cell cache.
3. **One changed container restarts all containers of its role on that host** (ansible-core loop-notify). With the
   default Nova settings, a nova-compute config change restarts **nova_libvirt** and **nova_ssh** with `nova_compute`
   on every compute ([Tags §2.4][readme-03-loop-notify]).
4. **Without batching, handlers restart a service on every host of the play at once.** Batching is `ANSIBLE_SERIAL` for
   `reconfigure`/`upgrade` and `-e kolla_serial=N` for `deploy`, which ignores `ANSIBLE_SERIAL`. Only MariaDB and
   RabbitMQ roll by themselves: their restarts run in separate plays with `serial: "33%"` (one node at a time with
   three nodes), and each RabbitMQ node is drained first ([Execution flow
   §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order)).
5. **A service tag is never just that service.** For a service with a frontend it also runs the haproxy frontend config
   (and can restart HAProxy). For API services it runs Keystone registration and DB sync. In 2023.1 it no longer runs
   `common` ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), [Reconfigure a single service
   §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)).
6. **`-t common` now does the work, and only it does.** `common` is its own play, tagged `common`, so fluentd, cron and
   kolla_toolbox changes need `-t common` or a run without tags; a service tag leaves them pending ([Tags
   §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code), [Apply `common`
   changes](../operations/apply-common-changes.md)). The Ussuri workaround `-t chrony` no longer exists.
7. **Global settings land in per-host files.** `enable_*`, RabbitMQ/memcached membership and passwords end up in
   compute-side configs, so small central changes cause fleet-wide restarts ([Why a small change creates a large
   workload](../risk/small-change-large-workload.md)).
8. **`deploy` never pulls an image that is already present.** Rebuilt images under the same tag need `pull`. A tag
   change applied with `deploy` recreates the entire fleet at once ([Update container
   images](../operations/update-container-images.md)).
9. **`--limit` does not contain everything.** Delegated tasks still run on `groups[x][0]` controllers, and all hosts'
   facts are gathered serially by the limited hosts ([Compute scaling](../concepts/compute-scaling-and-performance.md),
   [Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node)).
10. **`--list-tasks` cannot predict a run.** Use `genconfig` plus `kolla_set_configs --check`, or staging ([Predict and
    inspect a run](../operations/predict-a-run.md)). Two things to know about the check:
    - **It compares only the files listed in `config.json`**, not its `command` or `permissions`: memcached lists no
      files, so a change to its command line never shows as drift. A plain `reconfigure` still applies it (the changed
      `config.json` notifies the restart handler), but once `genconfig` has written it, no later run restarts the
      container for it; it takes effect at the next restart for another reason ([Write config first, apply in controlled
      batches §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern)).
    - **A newly rendered optional file** whose destination is not yet in the container makes `--check` exit 1, so the
      container restarts and the file is copied. In Ussuri the same case made the check exit 2 and the task fail
      ([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

## Related

- [Find it fast](find-it-fast.md) — typical operator questions and the section that answers them
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — what to check before a run
- [Risk register](../risk/risk-register.md) — the risks [R1–R25](../risk/risk-register.md#r1), with their precautions
  (R25 does not apply to 2023.1)
- [Technical findings](../reference/findings.md) — the fifteen headline findings, each with its evidence
- [Operations](../operations/index.md) — the operation pages, each with its commands

[readme-03-loop-notify]: ../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code
