---
title: Pre-execution checklist
description: In 2025.1, the eight checks to make before every production run of kolla-ansible, and what to add on the first 2025.1 run after 2024.1.
tags: [genconfig, kolla-set-configs, serial, max-fail-percentage, pull, limit, mariadb-backup, prechecks, quorum-queues, systemd, risk]
remember:
  - "Before every production run: know the diff, the restart set and the batch size; pull first; health gates and workload gates; scope; rollback material."
  - "Run <code>kolla-ansible genconfig</code> with the same tags and <code>--limit</code>: it writes config and, apart from two narrow cases, restarts no container. Then diff <code>/etc/kolla/&lt;service&gt;/</code> against the previous version. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: only the containers that drifted restart, and a service tag no longer restarts HAProxy. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: <code>reconfigure</code> and <code>upgrade</code> always run every host at once (<code>kolla_serial=0</code>); batch with <code>deploy -e kolla_serial=N</code> or <code>--limit</code>. mariadb and rabbitmq restart with a fixed <code>serial: \"33%\"</code>, etcd has no <code>serial</code>, and with the default <code>max_fail_percentage</code> of 100 a failed host only drops out, unless every host of a batch fails. <span class=\"ev ev-code\">CODE</span>"
  - "First 2025.1 run after 2024.1: classic RabbitMQ queues must be gone, units without <code>PartOf=kolla.target</code> restart, Docker containers outside the Red Hat family are recreated for the new ulimits, and a <code>deploy</code> or <code>reconfigure</code> moves every service that <code>kolla-ansible upgrade</code> has not reached to its 2025.1 image. <span class=\"ev ev-code\">CODE</span>"
impact: [writes-config]
scenarios:
  - title: "Live migrations still running on the target hosts"
    situation: "You are about to run a <code>deploy -e kolla_serial=10</code> on a batch of 10 computes in a cloud with 40 computes. Just before starting, <code>openstack server list --all-projects --status MIGRATING</code> shows two live migrations in flight on hosts of your batch. Your colleague says the run will not take long and suggests starting anyway."
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
        why: "Keeping the previous image tags is right, but step 8 lists more rollback material: the previous <code>/etc/kolla/config</code>, <code>globals.yml</code>, <code>passwords.yml</code> and inventory under git, and a MariaDB backup (<code>kolla-ansible mariadb-backup</code>, which needs <code>enable_mariabackup: \"yes\"</code> applied beforehand)."
      - text: "Keep the previous image tags until you are done, and gather all the rollback material before the run: config, <code>globals.yml</code>, <code>passwords.yml</code> and inventory under git, plus a MariaDB backup with <code>kolla-ansible mariadb-backup</code>, checking that a backup file was produced."
        verdict: "best"
        why: "Step 8, rollback material: previous image tags still present locally (do not <code>prune-images</code> before you are done), the previous configuration and inventory under git, and a MariaDB backup. <code>mariadb-backup</code> does nothing unless <code>enable_mariabackup</code> is <code>\"yes\"</code> (default <code>\"no\"</code>) <span class=\"ev ev-code\">CODE</span>."
      - text: "Run <code>kolla-ansible prune-images</code> now, then start the upgrade."
        verdict: "avoid"
        why: "Step 8 says it directly: do not <code>prune-images</code> before you are done. It prunes Kolla images by their <code>kolla_version</code> label; which ones it removes depends on the prune defaults of Docker or Podman <span class=\"ev ev-na\">NOT AVAILABLE</span>."
    see: "1-the-checklist"
  - title: "Prechecks fail on the first 2025.1 run"
    situation: "You moved the deployment host to Kolla-Ansible 2025.1. Your 2024.1 cloud kept classic mirrored queues with <code>om_enable_rabbitmq_high_availability: true</code>. <code>kolla-ansible prechecks -i multinode</code> fails on \"Check if RabbitMQ quorum queues need to be configured\", naming a non-quorum queue. A colleague proposes to run <code>prechecks</code> again with <code>--skip-tags rabbitmq-ha-precheck</code>, which passes, and to go ahead."
    ask: "What would you do?"
    choices:
      - text: "Use the run with the skipped tag: it passes, so the platform is ready."
        verdict: "avoid"
        why: "Skipping the tag only skips the queue assertions; it does not change what the services render. In 2025.1 every service renders <code>rabbit_quorum_queue = true</code> unconditionally, and the HA option no longer exists <span class=\"ev ev-code\">CODE</span>."
      - text: "Plan the migration to quorum queues (and transient quorum and stream fanout queues) first, as the precheck message says, then run untagged <code>prechecks</code> again before any other run."
        verdict: "best"
        why: "In 2025.1 quorum queues are the only choice: <code>om_enable_rabbitmq_quorum_queues</code> and <code>om_enable_rabbitmq_high_availability</code> are gone, and the precheck fails on any classic queue while a <code>rabbitmq</code> container exists <span class=\"ev ev-code\">CODE</span>. The precheck message calls the migration manual and says it may take several hours on larger systems. What oslo.messaging does with existing classic queues is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>."
      - text: "Keep <code>om_enable_rabbitmq_high_availability: true</code> in <code>globals.yml</code>, as in 2024.1."
        verdict: "avoid"
        why: "The variable no longer exists in 2025.1: nothing reads it, so it keeps nothing <span class=\"ev ev-code\">CODE</span>."
    see: "2-first-20251-run-on-a-cloud-deployed-by-20241"
quiz:
  - q: "What should you run before <code>upgrade</code> or <code>deploy</code>, so that restart windows do not include downloads?"
    options: ["<code>kolla-ansible pull</code>, with the same tags", "<code>kolla-ansible prechecks</code>", "Nothing: there is no way to avoid downloads during restarts"]
    answer: 0
    explain: "Step 4 of the checklist: pull first."
    see: "1-the-checklist"
  - q: "Can you batch a <code>reconfigure</code> with <code>-e kolla_serial=5</code> in 2025.1?"
    options: ["Yes, like every other command", "No: <code>reconfigure</code> always passes <code>kolla_serial=0</code> after your <code>-e</code>; use <code>deploy -e kolla_serial=5</code> or <code>--limit</code>"]
    answer: 1
    explain: "Step 3: the 2025.1 CLI adds <code>kolla_serial=0</code> for <code>reconfigure</code> and <code>upgrade</code>, after the user's extra vars <span class=\"ev ev-code\">CODE</span>."
    see: "1-the-checklist"
  - q: "Do <code>mariadb</code> and <code>rabbitmq</code> follow <code>kolla_serial</code>?"
    options: ["Yes, like every other role", "No, they ignore it"]
    answer: 1
    explain: "Their role plays have no <code>serial</code>, and their restart plays use a fixed <code>serial: \"33%\"</code> (step 3). The etcd play has no <code>serial</code> either."
    see: "1-the-checklist"
  - q: "After a 2024.1 → 2025.1 upgrade, <code>kolla_set_configs --check</code> exits 0 in a container. Can the next <code>reconfigure</code> still restart it?"
    options: ["No: 0 means the container will not restart", "Yes: its systemd unit may still be the one 2024.1 wrote, and the whole unit text is compared"]
    answer: 1
    explain: "The check step also compares the unit file with the 2025.1 template; a unit without <code>PartOf=kolla.target</code> differs, so the container restarts <span class=\"ev ev-code\">CODE</span>."
    see: "2-first-20251-run-on-a-cloud-deployed-by-20241"
---

# Pre-execution checklist

What to check before running `kolla-ansible` against a production cloud, read in Kolla-Ansible `2025.1-eom`. The
checklist of [§1](#1-the-checklist) applies to every production run;
[§2](#2-first-20251-run-on-a-cloud-deployed-by-20241) adds what the first 2025.1 run on a cloud deployed by 2024.1
needs.

> [!NOTE]
> **Key answers**
>
> - **Before every production run:** the pre-execution checklist. Know the diff, the restart set and the batch size;
>   pull first; health gates and workload gates; scope; rollback material (steps 1 to 8 of [§1](#1-the-checklist)).
> - **Changed in 2025.1:** only drifted containers restart; a service tag no longer restarts HAProxy; `reconfigure` and
>   `upgrade` cannot be batched with `kolla_serial` ([F19](../reference/findings.md#f19)) [CODE].
> - **First 2025.1 run after 2024.1:** classic RabbitMQ queues must be migrated first; the systemd unit text changed;
>   with Docker outside the Red Hat family, the default ulimits changed; a `deploy` or `reconfigure` moves every
>   service that `kolla-ansible upgrade` has not reached to its 2025.1 image. Run untagged `prechecks`, migrate the
>   queues, upgrade first, and list the affected containers before the run [CODE]
>   ([§2](#2-first-20251-run-on-a-cloud-deployed-by-20241)).

## 1. The checklist

1. **Know the diff before you run.**
   - Run `kolla-ansible genconfig` with the same tags and `--limit`. **Changed in 2025.1:** this writes config and, apart
     from two narrow cases, restarts no container: the config tasks no longer notify the restart handlers, which come
     from the shared check step that `genconfig` does not run; the two config tasks that still notify can restart
     `placement-api` (with `placement_wsgi_provider: apache`) and `cinder-volume` (with Huawei XML files)
     (`kolla_ansible/cli/commands.py:113-125`; [Execution
     flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)). It no longer
     pulls the fluentd image.
   - `genconfig` also re-renders `/etc/kolla/haproxy/services.d/` for the tagged services (`site.yml:325-327`,
     `roles/haproxy-config/tasks/main.yml:2-21`), while the loadbalancer check step is skipped under `config`
     (`site.yml:319-324`). In 2025.1 a frontend change reaches HAProxy only through `-t haproxy reconfigure` or an
     untagged run, and that restart is staged, backups first and the VIP holder last
     (`roles/loadbalancer/handlers/main.yml:9-34`). Copy `services.d` before `genconfig` to diff it.
   - Then diff `/etc/kolla/<service>/` against the previous version. Keep `/etc/kolla` under version control on
     every host, or snapshot it before the run.
   - On each container, `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` (Podman: `podman exec -u
     root`) tells you whether its configuration *will* make it restart (exit 1 = the command of `config.json` differs
     from the running one, a recorded file is no longer listed (both new in 2025.1), a listed file differs or is missing
     from the container, a new `optional` file included, a required source is missing or `config.json` is invalid;
     exit 2 = unexpected error, such as a `config.json` that cannot be opened, which fails the check task on that host
     instead of restarting, when the comparison reaches the config check: it is skipped when the container is missing or
     its parameters already differ, `module_utils/kolla_container_worker.py:58-65`; with Podman, 137 fails the task
     too, where Docker treats it as drift). The check does not see a changed image, volume, dimension or systemd unit,
     which restart the container as well (`module_utils/kolla_container_worker.py:58-89`). See [Predict and inspect a
     run](predict-a-run.md) and [Kolla
     images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes).
2. **Know the restart set.** **Changed in 2025.1:** only the containers that the check step found changed restart; the
   loop-notify of earlier releases, which restarted every container of the role on that host, is gone
   (`roles/service-check-containers/tasks/main.yml:4-41`; [Tags
   §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). A service tag never restarts HAProxy
   ([Reconfigure a single service](reconfigure-a-service.md)).
3. **Know the batch size.**
   - **Changed in 2025.1:** `reconfigure` and `upgrade` always pass `kolla_serial=0` after the user's `-e`, so they run
     every host of a play at once (`kolla_ansible/cli/commands.py:20-22, :136, :278`;
     [F19](../reference/findings.md#f19)). `-e kolla_serial=N` covers `deploy`, `deploy-containers`, `stop`, `pull` and
     `bootstrap-servers` (the plays read `serial: '{{ kolla_serial|default("0") }}'`, e.g. `site.yml:95`). To batch a
     configuration change, run `deploy` (the same tasks as `reconfigure`) with `-e kolla_serial=N`, or split the hosts
     with `--limit`.
   - mariadb and rabbitmq ignore it: their role plays have no `serial` and their restart plays use a fixed
     `serial: "33%"` (`mariadb.yml:24, :42`; `rabbitmq.yml:36`).
   - The etcd play has no `serial` (`site.yml:485-496`); its handlers stage the restarts themselves ([Controlled batches
     §1.2](controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure)).
   - cyborg uses the wrong variable (`serial: '{{ serial|default("0") }}'`, `site.yml:874`).
   - Every play sets `max_fail_percentage`, from `<service>_max_fail_percentage`, then `kolla_max_fail_percentage`,
     then 100 (e.g. `site.yml:96-99`). With 100 a failed host only drops out and the next batches run, unless every
     host of a batch fails: ansible-core then stops the playbook (ansible-core 2.18.20
     `lib/ansible/executor/playbook_executor.py:199-203`), so with `-e kolla_serial=1`, or in the 33% restart plays of
     a three-node mariadb or rabbitmq, one failed host ends the run. To stop a rolling run at the first bad batch, set
     `kolla_max_fail_percentage` lower ([Controlled
     batches §1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
4. **Pull first.** `kolla-ansible pull` (with the same tags, `kolla_ansible/cli/commands.py:173-184`) before
   `upgrade`/`deploy`, so that restart windows do not include downloads.
5. **Health gates.** Before the run, check:
   - Galera: `wsrep_cluster_size`, `wsrep_local_state_comment=Synced`;
   - RabbitMQ: cluster status, no partitions;
   - `openstack compute service list` and `openstack network agent list` all up;
   - HAProxy backends all UP.

   Repeat after each batch. **New in 2025.1:** `kolla-ansible check` fails a host when one of its Kolla containers is
   missing, not running or unhealthy ([Execution
   flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)); how it behaves on a
   real cloud is [NOT AVAILABLE].
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
   - `-t common` runs the common role (fluentd, kolla-toolbox, cron) in its own play. Service tags do not run common:
     no 2025.1 role has a `meta` dependency on it (`site.yml:88-103`, `roles/common/tasks/main.yml:2`).
8. **Rollback material.**
   - Previous `/etc/kolla/config`, `globals.yml`, `passwords.yml` and inventory under git.
   - Previous image tags still present locally: do not run `prune-images` before you are done. It runs
     `docker_prune` (or `podman image prune`) filtered on the `kolla_version` label
     (`roles/prune-images/tasks/prune_images.yml:2-16`); [NOT AVAILABLE] which images that removes, dangling only or
     tagged ones too: it depends on the prune defaults of Docker or Podman.
   - A MariaDB backup (**renamed in 2025.1** `kolla-ansible mariadb-backup`, `kolla_ansible/cli/commands.py:437-467`;
     [Database operations](database-operations.md)). It works only with `enable_mariabackup: "yes"` set and applied
     to mariadb beforehand: the playbook applies the role only when that flag is true (`mariadb_backup.yml:8-11`), the
     default is `"no"` (`group_vars/all.yml:922`), and the mariabackup config is rendered only with it
     (`roles/mariadb/tasks/config.yml:12-57`). Otherwise the command skips silently: check that a backup file was
     produced.

## 2. First 2025.1 run on a cloud deployed by 2024.1

On the first `deploy`, `reconfigure`, `deploy-containers` or `upgrade` that the 2025.1 code runs, changes in the code
restart or recreate containers even when the operator changed nothing, and the image tag changes for every service not
yet upgraded. Add these checks to §1 [CODE]:

1. **Migrate the RabbitMQ queues first** ([F17](../reference/findings.md#f17)).
   - `om_enable_rabbitmq_quorum_queues` and `om_enable_rabbitmq_high_availability` are gone: every service renders
     `rabbit_quorum_queue = true` and `rabbit_transient_quorum_queue = true`, and `rabbit_stream_fanout = true` while
     `om_enable_rabbitmq_stream_fanout` keeps its default `true` (`group_vars/all.yml:287, :292`; e.g.
     `roles/nova-cell/templates/nova.conf.j2:201-206`). A cloud that kept classic mirrored queues in 2024.1 has no way
     to keep them.
   - Run `kolla-ansible prechecks` **without** `-t`: the `prechecks` role is an untagged play (`site.yml:77-86`), so a
     tagged run skips its checks. When a `rabbitmq` container exists, the rabbitmq precheck lists the queues and fails
     on any non-quorum queue (except `reply_` and `_fanout` ones), on non-quorum `reply_` queues, and on `_fanout`
     queues that are not streams while stream fanout is on (`roles/rabbitmq/tasks/precheck.yml:110-163`); those
     assertions carry the tag `rabbitmq-ha-precheck` (`:164`), and skipping it does not change what the services
     render. The CI upgrade job skips that tag, then migrates the queues (`tests/upgrade.sh:21-22`).
   - The precheck message calls the migration manual and says it may take several hours on larger systems
     (`roles/rabbitmq/tasks/precheck.yml:121-125`). [NOT AVAILABLE] What oslo.messaging does with existing classic
     queues when the services restart with these options.
2. **List the units that 2024.1 wrote** ([F16](../reference/findings.md#f16)). The check step compares the whole unit
   file with the 2025.1 template, which adds `PartOf=kolla.target` (`module_utils/kolla_systemd_worker.py:20-40, :27,
   :155-168`). On each host, `grep -L PartOf=kolla.target /etc/systemd/system/kolla-*-container.service` lists the
   containers that the next check will restart, even when `kolla_set_configs --check` exits 0. A container that a
   2025.1 run created, recreated or restarted (an upgrade that reached its role does one of these) already has the new
   unit; after a partial upgrade (`upgrade -t <svc>`), every other service still has the old one. Plan those restarts
   in batches with `deploy -e kolla_serial=N` or `--limit` ([Controlled batches](controlled-batches.md)).
3. **Expect recreations for the new ulimits** (Docker, hosts outside the Red Hat family).
   `default_container_dimensions` now carries a `nofile` ulimit with Docker on every host (`group_vars/all.yml:201-224`);
   containers created by 2024.1 on such hosts lack it, so they differ and are recreated at the first check
   (`module_utils/kolla_container_worker.py:274-303, :326-336`; [Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)). Podman
   hosts are not affected.
4. **Upgrade every service before any `deploy` or `reconfigure`.** `openstack_release` defaults to `2025.1`
   (`group_vars/all.yml:795-797`) and every image tag follows it (e.g. `roles/keystone/defaults/main.yml:98-100`). The
   check step compares the image (`module_utils/kolla_container_worker.py:75`), and the restart handler recreates a
   container whose image differs, pulling the image first when it is absent
   (`module_utils/kolla_docker_worker.py:352-372`). So a `deploy` or `reconfigure` moves every service that
   `kolla-ansible upgrade` has not yet reached (all of them before the upgrade, the services outside the tags after
   `upgrade -t <svc>`) to its 2025.1 image through the deploy path, without the role's upgrade tasks (e.g. keystone's
   database upgrade handlers, `roles/keystone/tasks/upgrade.yml:23-34`). `kolla_set_configs --check` does not show it.
   Run `kolla-ansible upgrade` for those services first. **New in 2025.1**, the CI upgrade job re-runs
   `bootstrap-servers` on the 2024.1 cloud before the upgrade (`tests/upgrade.sh:16-20`); what that run changes on the
   hosts is in [Fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md).

[NOT AVAILABLE] The effect of these restarts and recreations on running VMs and volumes: the sources do not establish
it. How to see each cause before the run: [Predict and inspect a run
§2](predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241).

## Related

- [Risk register](../risk/risk-register.md) — the risks, each with its precautions
- [Predict and inspect a run](predict-a-run.md) — the commands of step 1, with the exit codes of the check
- [Write config first, apply in controlled batches](controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch, and `max_fail_percentage`
- [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code) — why only the drifted container restarts (step 2)
- [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) —
  batching with `serial`, and the plays that are not batched (step 3)
- [Update container images](update-container-images.md) — `pull` before `upgrade` (step 4)
- [Database operations](database-operations.md) — the `mariadb-backup` command of step 8
- [Technical findings F16, F17, F19](../reference/findings.md#f16) — the unit-text drift, the quorum-only RabbitMQ
  and the unbatchable `reconfigure` of §1 and §2
- [RabbitMQ](../components/rabbitmq.md) — the quorum-only queues and the stricter prechecks
- [2024.1 pre-execution checklist](../../2024.1/operations/pre-execution-checklist/) — the same page for 2024.1
