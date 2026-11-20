---
title: Pre-execution checklist
description: The eight checks to make before every production run of kolla-ansible, from knowing the diff to keeping rollback material.
tags: [genconfig, kolla-set-configs, loop-notify, serial, pull, limit, mariadb-backup, risk]
remember:
  - "Before every production run: know the diff, the restart set and the batch size; pull first; health gates and workload gates; scope; rollback material."
  - "Run <code>kolla-ansible genconfig</code> with the same tags and <code>--limit</code>: it writes config without restarting containers, except unguarded nova-hyperv handlers, so keep Hyper-V hosts out of the <code>--limit</code>."
  - "Loop-notify: if one container of a role changes on a host, every container of that role on that host restarts."
  - "<code>ANSIBLE_SERIAL</code> covers <code>reconfigure</code>/<code>upgrade</code> and <code>-e kolla_serial=N</code> covers <code>deploy</code>; mariadb and rabbitmq ignore it."
  - "Check Galera, RabbitMQ, compute services, network agents and HAProxy backends before the run and after each batch, with no migrations, resizes or uploads in flight."
impact: [writes-config]
scenarios:
  - title: "Live migrations still running on the target hosts"
    situation: "You are about to run a <code>reconfigure</code> on a batch of 10 computes in a cloud with 40 computes. Just before starting, <code>openstack server list --all-projects --status MIGRATING</code> shows two live migrations in flight on hosts of your batch. Your colleague says the run will not take long and suggests starting anyway."
    ask: "What would you do?"
    choices:
      - text: "Start the run now on the whole batch: the migrations will finish on their own during the run."
        verdict: "avoid"
        why: "This breaks the workload gate of step 6: no live migrations, resizes, image uploads or volume migrations in flight on the targeted hosts."
      - text: "Start the run now, but without <code>--limit</code>, so that the whole cloud is done in one pass."
        verdict: "avoid"
        why: "It still targets the hosts with migrations in flight (step 6), and step 7 says the opposite: prefer <code>--limit</code> and the narrowest tag."
      - text: "Wait until nothing is in flight on the targeted hosts (check each server status such as <code>MIGRATING</code> and <code>RESIZE</code> with <code>openstack server list --all-projects --host &lt;host&gt; --status &lt;status&gt;</code>, and the volumes the same way), check the health gates, then run on the batch with <code>--limit</code>."
        verdict: "best"
        why: "This is steps 5 to 7 of the checklist: no live migrations, resizes, image uploads or volume migrations in flight on the targeted hosts; health gates (Galera, RabbitMQ, compute services and network agents, HAProxy backends) before the run and after each batch; prefer <code>--limit</code> and the narrowest tag."
  - title: "Free disk space before an upgrade"
    situation: "You have pulled the new images with <code>kolla-ansible pull</code> before tonight's <code>upgrade</code>, and some hosts are short of disk space. Your colleague suggests running <code>kolla-ansible prune-images</code> now to free space, then starting the upgrade."
    ask: "What would you do?"
    choices:
      - text: "Keep the previous images, but skip the MariaDB backup: the old images are enough to go back."
        verdict: "risky"
        why: "Keeping the previous image tags is right, but step 8 lists more rollback material: the previous <code>/etc/kolla/config</code>, <code>globals.yml</code>, <code>passwords.yml</code> and inventory under git, and a MariaDB backup (<code>kolla-ansible mariadb_backup</code>, which does nothing unless <code>enable_mariabackup</code> is on)."
      - text: "Keep the previous image tags until you are done, and gather all the rollback material before the run: config, <code>globals.yml</code>, <code>passwords.yml</code> and inventory under git, plus a MariaDB backup that you checked was really produced (<code>kolla-ansible mariadb_backup</code> needs <code>enable_mariabackup</code> on)."
        verdict: "best"
        why: "Step 8, rollback material: previous image tags still present locally (do not <code>prune-images</code> before you are done), the previous configuration and inventory under git, and a MariaDB backup."
      - text: "Run <code>kolla-ansible prune-images</code> now, then start the upgrade."
        verdict: "avoid"
        why: "Step 8 says it directly: keep the previous image tags present locally and do not <code>prune-images</code> before you are done."
quiz:
  - q: "What should you run before <code>upgrade</code> or <code>deploy</code>, so that restart windows do not include downloads?"
    options: ["<code>kolla-ansible pull</code>, with the same tags", "<code>kolla-ansible prechecks</code>", "Nothing: there is no way to avoid downloads during restarts"]
    answer: 0
    explain: "Step 4 of the checklist: pull first."
  - q: "Do <code>mariadb</code> and <code>rabbitmq</code> follow <code>ANSIBLE_SERIAL</code>?"
    options: ["Yes, like every other role", "No, they ignore it"]
    answer: 1
    explain: "They ignore it and always run all hosts in one batch (step 3)."
  - q: "What does <code>-t common</code> do?"
    options: ["Nothing: it is a no-op", "It runs the common role (fluentd, kolla-toolbox, cron) in its own play"]
    answer: 0
    explain: "Never use <code>-t common</code> expecting it to do something <span class=\"ev ev-code\">CODE</span> (step 7)."
---

# Pre-execution checklist

What to check before running `kolla-ansible` against a production cloud. The checklist applies to every production run.

> [!NOTE]
> **Key answers**
>
> - **Before every production run:** the pre-execution checklist. Know the diff, the restart set and the batch size;
>   pull first; health gates and workload gates; scope; rollback material (steps 1 to 8 below).

1. **Know the diff before you run.**
   - Run `kolla-ansible genconfig` with the same tags and `--limit`. This writes config but does not restart any
     Docker container: every container restart handler has `when: kolla_action != "config"`, and the handlers
     without that guard are no-ops, steps chained to guarded handlers, or bootstrap, check-containers or upgrade
     steps that genconfig never notifies. Exception: the deprecated nova-hyperv role's handlers
     (`roles/nova-hyperv/handlers/main.yml:2-15`) are unguarded and are notified directly by its `config.yml`, so
     with `enable_hyperv` genconfig can restart the Windows nova-compute, neutron-hyperv-agent and FreeRDP-WebConnect
     services; keep Hyper-V hosts out of the `--limit`.
   - Then diff `/etc/kolla/<service>/` against the previous version. Keep `/etc/kolla` under version control on
     every host, or snapshot it before the run.
   - On each container, `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` tells you whether it *will*
     be restarted (exit 1 = a listed file differs, a required source is missing or `config.json` is invalid; exit 2 =
     error, including a new optional file not yet in the container, which fails the check-containers task on that host
     instead of restarting; see [Predict and inspect a run](predict-a-run.md) and [Kolla images
     §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
2. **Know the restart set.** Remember loop-notify: if one container of a role changes on a host, every container of that
   role on that host restarts ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
3. **Know the batch size.**
   - `ANSIBLE_SERIAL` covers `reconfigure`/`upgrade`; `-e kolla_serial=N` covers `deploy`.
   - mariadb and rabbitmq ignore it.
   - cyborg uses the wrong variable.
4. **Pull first.** `kolla-ansible pull` (with the same tags) before `upgrade`/`deploy`, so that restart windows do not
   include downloads.
5. **Health gates.** Before the run, check:
   - Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`;
   - RabbitMQ: cluster status, no partitions;
   - `openstack compute service list` and `openstack network agent list` all up;
   - HAProxy backends all UP.

   Repeat after each batch.
6. **Workload gates.** No live migrations, resizes, image uploads or volume migrations in flight on the targeted
   hosts. This gate is operator practice, not read from the code. Check each in-progress status separately, for
   example `openstack server list --all-projects --host <host> --status MIGRATING` (then `RESIZE` and
   `VERIFY_RESIZE`) and `openstack volume list --all-projects --status <status>` for each in-progress volume status;
   image uploads need their own check.
7. **Scope.**
   - Prefer `--limit` and the narrowest tag.
   - Add `--skip-tags haproxy` when the frontends are not meant to change.
   - Never use `-t common` expecting it to do something.
8. **Rollback material.**
   - Previous `/etc/kolla/config`, `globals.yml`, `passwords.yml` and inventory under git.
   - Previous image tags still present locally (do not `prune-images` before you are done).
   - A MariaDB backup. `kolla-ansible mariadb_backup` does nothing unless `enable_mariabackup` is `"yes"` and was
     applied to MariaDB beforehand: the default is `"no"` (`group_vars/all.yml:661`) and the play applies the role
     only `when: enable_mariabackup | bool` (`mariadb_backup.yml:7`) [CODE]. Check that a backup was really produced.

## Related

- [Risk register](../risk/risk-register.md) — the 25 risks, each with its precautions
- [Predict and inspect a run](predict-a-run.md) — the commands of step 1, with the exit codes of the check
- [Write config first, apply in controlled batches](controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify,
  the mechanism of step 2
- [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) —
  batching with `serial`, and the plays that are not batched (step 3)
- [Update container images](update-container-images.md) — `pull` before `upgrade` (step 4)
- [Database operations](database-operations.md) — the `mariadb_backup` command of step 8
