---
title: Pre-execution checklist
description: In 2024.1, the eight checks to make before every production run of kolla-ansible, and what to add on the first 2024.1 run after 2023.1.
tags: [genconfig, kolla-set-configs, loop-notify, serial, max-fail-percentage, pull, limit, mariadb-backup, prechecks, quorum-queues, systemd, risk]
remember:
  - "Before every production run: know the diff, the restart set and the batch size; pull first; health gates and workload gates; scope; rollback material."
  - "Run <code>kolla-ansible genconfig</code> with the same tags and <code>--limit</code>: it writes config and restarts no container, but an untagged or <code>-t common</code> run can pull the fluentd image. Then diff <code>/etc/kolla/&lt;service&gt;/</code> against the previous version. <span class=\"ev ev-code\">CODE</span>"
  - "Loop-notify: if one container of a role changes on a host, every container of that role on that host restarts. <span class=\"ev ev-code\">CODE</span>"
  - "<code>ANSIBLE_SERIAL</code> covers <code>reconfigure</code>/<code>upgrade</code>; mariadb and rabbitmq restart with a fixed <code>serial: \"33%\"</code>, etcd has no <code>serial</code>, and with the default <code>max_fail_percentage</code> of 100 a failed host only drops out, unless every host of a batch fails: then the playbook stops. <span class=\"ev ev-code\">CODE</span>"
  - "First 2024.1 run after 2023.1: units with <code>StartLimitIntervalSec=</code>, the new <code>hostnqn</code> file and <code>rabbit_quorum_queue = true</code> each restart containers, and a <code>deploy</code> or <code>reconfigure</code> moves every service that <code>kolla-ansible upgrade</code> has not reached to its 2024.1 image; run untagged <code>prechecks</code>, settle the queue type and upgrade first. <span class=\"ev ev-code\">CODE</span>"
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
      - text: "Wait until <code>openstack server list --all-projects --host &lt;host&gt; --status MIGRATING</code> (and the same with <code>RESIZE</code> and <code>VERIFY_RESIZE</code>) and the volume and image checks of step 6 show nothing in flight on the targeted hosts, check the health gates, then run on the batch with <code>--limit</code>."
        verdict: "best"
        why: "This is steps 5 to 7 of the checklist: no live migrations, resizes, image uploads or volume migrations in flight on the targeted hosts; health gates (Galera, RabbitMQ, compute services and network agents, HAProxy backends) before the run and after each batch; prefer <code>--limit</code> and the narrowest tag."
    see: "1-the-checklist"
  - title: "Free disk space before an upgrade"
    situation: "You have pulled the new images with <code>kolla-ansible pull</code> before tonight's <code>upgrade</code>, and some hosts are short of disk space. Your colleague suggests running <code>kolla-ansible prune-images</code> now to free space, then starting the upgrade."
    ask: "What would you do?"
    choices:
      - text: "Keep the previous images, but skip the MariaDB backup: the old images are enough to go back."
        verdict: "risky"
        why: "Keeping the previous image tags is right, but step 8 lists more rollback material: the previous <code>/etc/kolla/config</code>, <code>globals.yml</code>, <code>passwords.yml</code> and inventory under git, and a MariaDB backup (<code>kolla-ansible mariadb_backup</code>, which needs <code>enable_mariabackup: \"yes\"</code> applied beforehand)."
      - text: "Keep the previous image tags until you are done, and gather all the rollback material before the run: config, <code>globals.yml</code>, <code>passwords.yml</code> and inventory under git, plus a MariaDB backup with <code>kolla-ansible mariadb_backup</code>, checking that a backup file was produced."
        verdict: "best"
        why: "Step 8, rollback material: previous image tags still present locally (do not <code>prune-images</code> before you are done), the previous configuration and inventory under git, and a MariaDB backup. <code>mariadb_backup</code> does nothing unless <code>enable_mariabackup</code> is <code>\"yes\"</code> (default <code>\"no\"</code>) <span class=\"ev ev-code\">CODE</span>."
      - text: "Run <code>kolla-ansible prune-images</code> now, then start the upgrade."
        verdict: "avoid"
        why: "Step 8 says it directly: do not <code>prune-images</code> before you are done. It prunes Kolla images by their <code>kolla_version</code> label; which ones it removes depends on the prune defaults of Docker or Podman <span class=\"ev ev-na\">NOT AVAILABLE</span>."
    see: "1-the-checklist"
  - title: "Prechecks fail on the first 2024.1 run"
    situation: "You moved the deployment host to Kolla-Ansible 2024.1 and kept every RabbitMQ option at its 2023.1 default. <code>kolla-ansible -i multinode prechecks</code> fails on \"Check if RabbitMQ quorum queues need to be configured\", naming a non-quorum queue. A colleague proposes to run <code>prechecks</code> again with <code>-t nova,neutron</code>, which passes, and to go ahead."
    ask: "What would you do?"
    choices:
      - text: "Use the tagged run: it passes, so the platform is ready."
        verdict: "avoid"
        why: "<code>-t &lt;svc&gt;</code> skips the untagged <code>prechecks</code> role and runs only the per-service prechecks, so the queue-type assertion of the rabbitmq role is simply not run <span class=\"ev ev-code\">CODE</span>. The services would still render <code>rabbit_quorum_queue = true</code> on the next run."
      - text: "Decide the queue type before any other run: either migrate to quorum queues (a procedure the precheck message calls manual), or set <code>om_enable_rabbitmq_quorum_queues: false</code> with <code>om_enable_rabbitmq_high_availability: true</code> and the <code>ha-all</code> policy; then run untagged <code>prechecks</code> again."
        verdict: "best"
        why: "Quorum on is the 2024.1 default, and <code>prechecks</code> fails when the two options are equal, so also when both are off; with quorum on it fails while classic queues exist <span class=\"ev ev-code\">CODE</span>. Keeping classic queues needs the <code>ha-all</code> policy, which 2023.1 runs removed on a cloud with HA off, so that path is also a manual migration, as the HA precheck message says, and HA on also renders <code>amqp_durable_queues = true</code> in the service configs <span class=\"ev ev-code\">CODE</span>. What oslo.messaging does with the existing classic queues is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>."
      - text: "Set <code>om_enable_rabbitmq_quorum_queues: false</code> and leave high availability off, as in 2023.1."
        verdict: "avoid"
        why: "It never passes <code>prechecks</code>: the 2024.1 <code>prechecks</code> role fails when both options are equal, both off included <span class=\"ev ev-code\">CODE</span>."
    see: "2-first-20241-run-on-a-cloud-deployed-by-20231"
quiz:
  - q: "What should you run before <code>upgrade</code> or <code>deploy</code>, so that restart windows do not include downloads?"
    options: ["<code>kolla-ansible pull</code>, with the same tags", "<code>kolla-ansible prechecks</code>", "Nothing: there is no way to avoid downloads during restarts"]
    answer: 0
    explain: "Step 4 of the checklist: pull first."
    see: "1-the-checklist"
  - q: "Do <code>mariadb</code> and <code>rabbitmq</code> follow <code>ANSIBLE_SERIAL</code>?"
    options: ["Yes, like every other role", "No, they ignore it"]
    answer: 1
    explain: "Their role plays have no <code>serial</code>, and their restart plays use a fixed <code>serial: \"33%\"</code> (step 3). In 2024.1 the etcd play has no <code>serial</code> either."
    see: "1-the-checklist"
  - q: "What does <code>-t common</code> do in 2024.1?"
    options: ["Nothing: it is a no-op", "It runs the common role (fluentd, kolla-toolbox, cron) in its own play"]
    answer: 1
    explain: "As in 2023.1, <code>common</code> is its own play, tagged <code>common</code>, and service tags do not run it (step 7). New in 2024.1, its config step can pull the fluentd image."
    see: "1-the-checklist"
  - q: "After a 2023.1 → 2024.1 upgrade, <code>kolla_set_configs --check</code> exits 0 in a container. Can the next <code>reconfigure</code> still restart it?"
    options: ["No: 0 means the container will not restart", "Yes: its systemd unit may still be the one 2023.1 wrote, and the whole unit text is compared"]
    answer: 1
    explain: "The check task also compares the unit file with the 2024.1 template; a unit that still holds <code>StartLimitIntervalSec=</code> differs, so the container restarts <span class=\"ev ev-code\">CODE</span>."
    see: "2-first-20241-run-on-a-cloud-deployed-by-20231"
---

# Pre-execution checklist

What to check before running `kolla-ansible` against a production cloud, read in Kolla-Ansible `2024.1-eom`. The
checklist of [§1](#1-the-checklist) applies to every production run;
[§2](#2-first-20241-run-on-a-cloud-deployed-by-20231)
adds what the first 2024.1 run on a cloud deployed by 2023.1 needs.

> [!NOTE]
> **Key answers**
>
> - **Before every production run:** the pre-execution checklist. Know the diff, the restart set and the batch size;
>   pull first; health gates and workload gates; scope; rollback material (steps 1 to 8 of [§1](#1-the-checklist)).
> - **First 2024.1 run after 2023.1:** three code changes restart containers whose operator config did not change: the
>   systemd unit text, the new `hostnqn` file, and quorum queues on by default. A fourth cause is the image: a `deploy`
>   or `reconfigure` moves every service that `kolla-ansible upgrade` has not reached to its 2024.1 image. Run untagged
>   `prechecks`, settle the queue type, upgrade first, and list the affected containers before the run [CODE]
>   ([§2](#2-first-20241-run-on-a-cloud-deployed-by-20231)).

## 1. The checklist

1. **Know the diff before you run.**
   - Run `kolla-ansible genconfig` with the same tags and `--limit`. This writes config but does not restart any
     container: every container restart handler has `when: kolla_action != "config"`, and the handlers without that
     guard are no-ops, steps chained to guarded handlers, or bootstrap, check-containers or upgrade steps that
     genconfig never notifies (`tools/kolla-ansible:557-560`; e.g. `roles/nova-cell/handlers/main.yml:89-90, :114-115,
     :167-168`; `roles/swift/handlers/main.yml:2-4`; [Execution
     flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)).
   - **New in 2024.1:** when the common play runs (no tag, or `-t common`), `genconfig` runs `kolla_container`
     `ensure_image` on the fluentd image, which pulls it when that tag is not on the host
     (`roles/common/tasks/config.yml:42-51`; `module_utils/kolla_docker_worker.py:501-503`). Pull first (step 4) or
     expect `genconfig` to need the registry.
   - `genconfig` also re-renders `/etc/kolla/haproxy/services.d/` for the tagged services (`site.yml:324-326`,
     `roles/haproxy-config/tasks/main.yml:2-23`), while every loadbalancer handler is skipped under `config`
     (`roles/loadbalancer/handlers/main.yml:16-17`). A later `-t <svc>` reconfigure then finds the file unchanged and
     does not restart HAProxy: a frontend change written by `genconfig` reaches HAProxy only through `-t haproxy
     reconfigure` or an untagged run, and that restart is staged, backups first and the VIP holder last
     (`roles/loadbalancer/handlers/main.yml:9-34`). Copy `services.d` before `genconfig` to diff it.
   - Then diff `/etc/kolla/<service>/` against the previous version. Keep `/etc/kolla` under version control on
     every host, or snapshot it before the run.
   - On each container, `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` (Podman: `podman exec -u
     root`) tells you whether its config files *will* make it restart (exit 1 = a listed file differs or is missing
     from the container, a new `optional` file included, a required source is missing or `config.json` is invalid;
     exit 2 = unexpected error, such as a `config.json` that cannot be opened, which fails the check task on that host
     instead of restarting, when the comparison reaches the config check: it is skipped when the container is missing or
     its parameters already differ, `module_utils/kolla_container_worker.py:58-65`; with Podman, 137 fails the task
     too, where Docker treats it as drift). The check does not
     see a changed image, volume or systemd unit, which restart the container as well
     (`module_utils/kolla_container_worker.py:58-65`). See [Predict and inspect a run](predict-a-run.md) and [Kolla
     images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes).
2. **Know the restart set.** Remember loop-notify: if one container of a role changes on a host, every container of that
   role on that host restarts ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
3. **Know the batch size.**
   - `ANSIBLE_SERIAL` covers `reconfigure`/`upgrade` (`tools/kolla-ansible:522, :531`); `-e kolla_serial=N` covers
     `deploy` (the plays read `serial: '{{ kolla_serial|default("0") }}'`, e.g. `site.yml:95`).
   - mariadb and rabbitmq ignore it: their role plays have no `serial` and their restart plays use a fixed
     `serial: "33%"` (`mariadb.yml:24, :42`; `rabbitmq.yml:36`).
   - **Changed in 2024.1:** the etcd play has no `serial` any more (`site.yml:470-481`); its handlers stage the
     restarts themselves ([Controlled batches §1.2](controlled-batches.md#12-rolling-reconfigure-with-ansible_serial)).
   - cyborg uses the wrong variable (`serial: '{{ serial|default("0") }}'`, `site.yml:876`).
   - **New in 2024.1:** every play sets `max_fail_percentage`, from `<service>_max_fail_percentage`, then
     `kolla_max_fail_percentage`, then 100 (e.g. `site.yml:96-99`). With 100 a failed host only drops out and the next
     batches run, unless every host of a batch fails: ansible-core then stops the playbook (ansible-core 2.16.20
     `lib/ansible/executor/playbook_executor.py:204-208`), so with `ANSIBLE_SERIAL=1`, or in the 33% restart plays of
     a three-node mariadb or rabbitmq, one failed host ends the run. To stop a rolling run at the first bad batch, set
     `kolla_max_fail_percentage` lower ([Controlled
     batches §1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
4. **Pull first.** `kolla-ansible pull` (with the same tags, `tools/kolla-ansible:516-518`) before `upgrade`/`deploy`,
   so that restart windows do not include downloads.
5. **Health gates.** Before the run, check:
   - Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`;
   - RabbitMQ: cluster status, no partitions;
   - `openstack compute service list` and `openstack network agent list` all up;
   - HAProxy backends all UP.

   Repeat after each batch.
6. **Workload gates.** No live migrations, resizes, image uploads or volume migrations in flight on the targeted
   hosts. `--status` takes one exact status, so run one command per status, for example `openstack server list
   --all-projects --host <host> --status MIGRATING`, then `RESIZE` and `VERIFY_RESIZE`; `openstack volume list
   --all-projects --status <status>` for each in-progress volume status; `openstack image list --status <status>` for
   uploads. Do not write `MIGRATING|RESIZE` or `*ing`: the shell reads them as a pipe and a file pattern. This gate is
   operator practice, not something the Kolla code checks.
7. **Scope.**
   - Prefer `--limit` and the narrowest tag.
   - Add `--skip-tags haproxy` when the frontends are not meant to change: every task of the loadbalancer play
     inherits its play tags `haproxy`, `keepalived` and `loadbalancer` (`site.yml:115-118`; [Tags
     §4](../risk/tags.md#4-practical-consequences)).
   - `-t common` runs the common role (fluentd, kolla-toolbox, cron) in its own play, as in 2023.1. Service tags do
     not run common: no 2024.1 role has a `meta` dependency on it (`site.yml:88-103`, `roles/common/tasks/main.yml:2`).
8. **Rollback material.**
   - Previous `/etc/kolla/config`, `globals.yml`, `passwords.yml` and inventory under git.
   - Previous image tags still present locally: do not run `prune-images` before you are done. It runs
     `docker_prune` (or `podman image prune`) filtered on the `kolla_version` label
     (`roles/prune-images/tasks/prune_images.yml:2-16`); [NOT AVAILABLE] which images that removes, dangling only or
     tagged ones too: it depends on the prune defaults of Docker or Podman.
   - A MariaDB backup (`kolla-ansible mariadb_backup`, `tools/kolla-ansible:453-456`). It works only with
     `enable_mariabackup: "yes"` set and applied to mariadb beforehand: the playbook applies the role only when that
     flag is true (`mariadb_backup.yml:8-11`), the default is `"no"` (`group_vars/all.yml:804`), and the mariabackup
     config is rendered only with it (`roles/mariadb/tasks/config.yml:17-64`). Otherwise the command skips silently:
     check that a backup file was produced.

## 2. First 2024.1 run on a cloud deployed by 2023.1

On the first `deploy`, `reconfigure`, `deploy-containers` or `upgrade` that the 2024.1 code runs, three changes in the
code restart containers even when the operator changed nothing, and the image tag changes for every service not yet
upgraded. Add these checks to §1 [CODE]:

1. **Settle the RabbitMQ queue type first** ([F17](../reference/findings.md#f17)).
   - `om_enable_rabbitmq_quorum_queues` now defaults to `true` (`group_vars/all.yml:266-268`), and every service
     config that renders `[oslo_messaging_rabbit]` then gets `rabbit_quorum_queue = true` (e.g.
     `roles/nova-cell/templates/nova.conf.j2:207-216`): a changed file, so a restart, for those services, computes
     included.
   - Run `kolla-ansible prechecks` **without** `-t`: the `prechecks` role is an untagged play (`site.yml:77-86`), so
     a tagged run skips its checks. It fails when `om_enable_rabbitmq_high_availability` and
     `om_enable_rabbitmq_quorum_queues` are equal, both off included (`roles/prechecks/tasks/service_checks.yml:67-72`).
     The rabbitmq precheck, when a `rabbitmq` container exists and quorum is on, asserts that every queue except
     `reply_` and `_fanout` ones is a quorum queue (`roles/rabbitmq/tasks/precheck.yml:131-152, :185-189`); those
     assertions carry the tag `rabbitmq-ha-precheck` (`:189`), and skipping it does not change what the services
     render.
   - Both settings that pass `prechecks` are migrations. Quorum on needs every existing queue converted to quorum
     queues. The only way to keep classic queues is `om_enable_rabbitmq_high_availability: true` with quorum off and
     the `ha-all` policy in place (`roles/rabbitmq/tasks/precheck.yml:107-129`); HA on also renders
     `amqp_durable_queues = true` in every service config (e.g. `roles/nova-cell/templates/nova.conf.j2:204-206`), a
     changed file, so a restart, for those services too. On a cloud that
     kept the 2023.1 default (HA off), 2023.1 runs removed `ha-all` (2023.1 kolla-ansible tree:
     ansible/roles/rabbitmq/tasks/deploy.yml, lines 4-6), so this path is also a manual migration, to mirrored queues,
     as the HA precheck message says (`roles/rabbitmq/tasks/precheck.yml:115-123`). [NOT AVAILABLE]
     What oslo.messaging does with existing classic queues when the services restart with quorum on.
2. **List the units that 2023.1 wrote** ([F16](../reference/findings.md#f16)). The check task compares the whole unit
   file with the 2024.1 template, which writes `StartLimitInterval=` and no longer `StartLimitIntervalSec=`
   (`module_utils/kolla_systemd_worker.py:20-39, :154-167`). On each host, `grep -l StartLimitIntervalSec
   /etc/systemd/system/kolla-*-container.service` lists the containers that the next check will restart (Swift `deploy`
   has no such check), with the
   rest of their role on that host, even when `kolla_set_configs --check` exits 0. A container that a 2024.1 run
   created, recreated or restarted (an upgrade that reached its role does one of these) already has the new unit; after
   a partial upgrade (`upgrade -t <svc>`), every other service
   still has the old one. Plan those restarts in batches with `--limit` ([Controlled
   batches](controlled-batches.md)).
3. **Expect the `hostnqn` restart on computes and cinder-volume hosts.** nova-cell and cinder render a new `hostnqn`
   file and notify the restart (`roles/nova-cell/tasks/config.yml:203-216`, `roles/cinder/tasks/config.yml:95-108`);
   `config.json` copies it, not optional, to `/etc/nvme/hostnqn`
   (`roles/nova-cell/templates/nova-compute.json.j2:59-63`,
   `roles/cinder/templates/cinder-volume.json.j2:23-27`). After `genconfig`, the check in `nova_compute` and
   `cinder_volume` exits 1. On a compute this restarts `nova_compute` and, by loop-notify, the other nova-cell
   containers of that host
   ([Nova deep dive §2.4](../components/nova-deep-dive.md#24-operational-dependencies-what-restarts-what)).
4. **Upgrade every service before any `deploy` or `reconfigure`.** `openstack_release` defaults to `2024.1`
   (`group_vars/all.yml:679-681`) and every image tag follows it (e.g. `roles/keystone/defaults/main.yml:96-100`). The
   check task compares the image (`module_utils/kolla_container_worker.py:75`), and the restart handler recreates a
   container whose image differs, pulling the image first when it is absent
   (`module_utils/kolla_docker_worker.py:353-361`). So a `deploy` or `reconfigure` moves every service that
   `kolla-ansible upgrade` has not yet reached (all of them before the upgrade, the services outside the tags after
   `upgrade -t <svc>`) to its 2024.1 image through the deploy path, without the role's upgrade tasks (e.g. keystone's
   database upgrade handlers, `roles/keystone/tasks/upgrade.yml:23-31`). `kolla_set_configs --check` does not show
   it. Run `kolla-ansible upgrade` for those services first.

[NOT AVAILABLE] The effect of these restarts on running VMs and volumes: the sources do not establish it. How to see
each cause before the run: [Predict and inspect a run
§2](predict-a-run.md#2-the-first-20241-run-on-a-cloud-deployed-by-20231).

## Related

- [Risk register](../risk/risk-register.md) — the risks, each with its precautions
- [Predict and inspect a run](predict-a-run.md) — the commands of step 1, with the exit codes of the check
- [Write config first, apply in controlled batches](controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch, and `max_fail_percentage`
- [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify,
  the mechanism of step 2
- [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) —
  batching with `serial`, and the plays that are not batched (step 3)
- [Update container images](update-container-images.md) — `pull` before `upgrade` (step 4)
- [Database operations](database-operations.md) — the `mariadb_backup` command of step 8
- [Technical findings F16, F17](../reference/findings.md#f16) — the unit-text drift and the quorum-queue default of
  §2
- [RabbitMQ](../components/rabbitmq.md) — the quorum-queue default and the stricter prechecks
