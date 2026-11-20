---
title: Ten things to know before a production run
description: Ten things to know before running Kolla-Ansible 2024.1 on production, each with the section that gives the evidence.
tags: [reconfigure, deploy, loop-notify, serial, tags, limit, images, kolla-set-configs, genconfig, handlers, risk]
remember:
  - "<code>reconfigure</code> is <code>deploy</code> for 52 of the 54 roles that have a <code>reconfigure.yml</code>; the only lightweight path is <code>genconfig</code> followed by <code>deploy-containers</code> <span class=\"ev ev-code\">CODE</span>."
  - "Config is applied by a full stop/start through the container's systemd unit, never a reload, and the stop timeout is 60 s, with Docker or Podman <span class=\"ev ev-code\">CODE</span>."
  - "One changed container restarts all containers of its role on that host; without batching, handlers restart it on every host of the play at once, and <code>deploy</code> needs <code>-e kolla_serial=N</code> <span class=\"ev ev-code\">CODE</span>."
  - "The first 2024.1 run on a cloud deployed by 2023.1 restarts containers whose operator config did not change: new unit text, the new <code>hostnqn</code> file, quorum queues on by default; and it moves every service that <code>kolla-ansible upgrade</code> has not reached to its 2024.1 image <span class=\"ev ev-code\">CODE</span>."
  - "<code>deploy</code> never pulls an image that is already present: rebuilt images under the same tag need <code>pull</code> <span class=\"ev ev-code\">CODE</span>."
quiz:
  - q: "What is the only lightweight path to apply config?"
    options: ["<code>reconfigure</code>", "<code>deploy</code> with a service tag", "<code>genconfig</code> followed by <code>deploy-containers</code>"]
    answer: 2
    explain: "<code>reconfigure</code> is <code>deploy</code> for 52 of the 54 roles that have a <code>reconfigure.yml</code> (swift and bifrost are the exceptions). The only lightweight path is <code>genconfig</code> followed by <code>deploy-containers</code> <span class=\"ev ev-code\">CODE</span>."
  - q: "You run <code>kolla-ansible deploy</code> with <code>ANSIBLE_SERIAL=1</code> set. How do the handlers restart a changed service?"
    options: ["One host at a time", "On every host of the play at once", "Only on the first host"]
    answer: 1
    explain: "For <code>deploy</code> the wrapper does not pass <code>ANSIBLE_SERIAL</code>; only <code>reconfigure</code> and <code>upgrade</code> do. Without batching, handlers restart a service on every host of the play at once: pass <code>-e kolla_serial=N</code> to <code>deploy</code> <span class=\"ev ev-code\">CODE</span>."
  - q: "In 2024.1, what applies fluentd, cron and kolla_toolbox changes?"
    options: ["Any service tag, which also runs <code>common</code>", "<code>-t common</code> or a run without tags", "<code>-t chrony</code>"]
    answer: 1
    explain: "<code>common</code> is its own play, tagged <code>common</code>, so these changes need <code>-t common</code> or a run without tags; a service tag leaves them pending <span class=\"ev ev-code\">CODE</span>."
  - q: "After the move from 2023.1, a <code>reconfigure</code> with no operator change restarts many containers. Which cause does <code>kolla_set_configs --check</code> not show?"
    options: ["The new <code>hostnqn</code> file of nova_compute", "The changed systemd unit text", "<code>rabbit_quorum_queue = true</code> in the service configs"]
    answer: 1
    explain: "The unit text is compared by <code>compare_container</code>, not by <code>kolla_set_configs --check</code>; the two other causes are config files that the check does report <span class=\"ev ev-code\">CODE</span>."
---

# Ten things to know before a production run

Ten things to know before running Kolla-Ansible 2024.1 on production. Each item restates a 2024.1 page and links to
the section that gives the evidence; the main citations are repeated here.

1. **`reconfigure` is `deploy`** for 52 of the 54 roles that have a `reconfigure.yml`: 51 import `deploy.yml` and
   skyline includes it (`roles/skyline/tasks/reconfigure.yml:2`); swift and bifrost are the exceptions. It re-runs
   Keystone registration, DB creation and the DB-sync bootstrap containers for most services, Neutron's included
   (`roles/neutron/tasks/bootstrap_service.yml:2-21`). The only lightweight path is `genconfig`
   (`tools/kolla-ansible:557-560`) followed by `deploy-containers` (`tools/kolla-ansible:499-502`) ([Repository
   architecture §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy), [Execution flow
   §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)) [CODE].
2. **Config is applied by a full stop/start, never a reload, and the stop timeout is 60 s.** Changed in 2024.1: the
   container module is `kolla_container`, which drives Docker or Podman according to `kolla_container_engine`
   (default `docker`, `group_vars/all.yml:92`; `library/kolla_container.py:415-420`). Containers run under systemd
   units whose stop is `<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:32`), with
   `docker_graceful_timeout: 60` (`group_vars/all.yml:139`); a service still running then is killed
   ([R24](../risk/risk-register.md#r24), [Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)) [CODE]. The
   only signal Kolla sends to a running container is a `SIGHUP` to `nova_scheduler`, which refreshes its cell cache
   (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10-12`). How the Podman path behaves on a real host is
   [NOT AVAILABLE].
3. **One changed container restarts all containers of its role on that host** (ansible-core loop-notify,
   `lib/ansible/plugins/strategy/__init__.py:648-661` in 2.16.20). With the default Nova settings, a nova-compute
   config change restarts **nova_libvirt** and **nova_ssh** with `nova_compute` on every compute
   (`roles/nova-cell/tasks/check-containers.yml:2-22`) ([Tags §2.4][readme-03-loop-notify]) [CODE].
4. **Without batching, handlers restart a service on every host of the play at once.** Batching is `ANSIBLE_SERIAL`
   for `reconfigure`/`upgrade` (`tools/kolla-ansible:522, :531`) and `-e kolla_serial=N` for `deploy`, which ignores
   `ANSIBLE_SERIAL` (`tools/kolla-ansible:490-493`). MariaDB and RabbitMQ roll by themselves: their restarts run in
   separate plays with `serial: "33%"` (`mariadb.yml:18-52`, `rabbitmq.yml:30-49`; one node at a time with three
   nodes), and each RabbitMQ node is drained first (`roles/rabbitmq/tasks/restart_services.yml:9-17`). Changed in
   2024.1: the etcd play has no `serial` (`site.yml:470-481`), and every play sets `max_fail_percentage`, 100 by
   default (`site.yml:96-99`): a failed host only drops out, unless every host of a batch fails, which stops the
   playbook (ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:204-208`); with `ANSIBLE_SERIAL=1` or in
   the
   33% restart plays of three nodes, one failure ends the run ([Execution flow
   §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order)) [CODE].
5. **A service tag is never just that service.** For a service with a frontend it also renders the haproxy frontend
   config on every loadbalancer host and, if that file changed, restarts HAProxy
   (`roles/haproxy-config/tasks/main.yml:22-23`),
   backups first and the VIP holder last (`roles/loadbalancer/handlers/main.yml:54-68, :179-193`). For API services it
   runs Keystone registration and DB sync. It does not run `common` ([Tags
   §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), [Reconfigure a single service
   §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)) [CODE].
   `--skip-tags haproxy` drops the whole loadbalancer play ([Reconfigure a single service
   §1.2](../operations/reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)).
6. **`-t common` does the work, and only it does.** `common` is its own play, tagged `common` (`site.yml:88-103`), so
   fluentd, cron and kolla_toolbox changes need `-t common` or a run without tags; a service tag leaves them pending
   ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code), [Apply `common`
   changes](../operations/apply-common-changes.md)) [CODE]. New in 2024.1: the common config step runs `ensure_image`
   on the fluentd image (`roles/common/tasks/config.yml:42-51`), so `-t common` and `genconfig` can pull it when it is
   absent.
7. **Global settings land in per-host files, and the first 2024.1 run changes some of them everywhere.** `enable_*`,
   RabbitMQ/memcached membership and passwords end up in compute-side configs, so small central changes cause
   fleet-wide restarts ([Findings F6](../reference/findings.md#f6), [Why a small change creates a large
   workload](../risk/small-change-large-workload.md)). On a cloud deployed by 2023.1, three code changes restart
   containers whose operator config did not change ([Predict and inspect a run
   §2](../operations/predict-a-run.md#2-the-first-20241-run-on-a-cloud-deployed-by-20231)) [CODE]:
   - **quorum queues on by default** ([F17](../reference/findings.md#f17)): `om_enable_rabbitmq_quorum_queues: true`
     (`group_vars/all.yml:266-268`) writes `rabbit_quorum_queue = true` into 26 templates of 24 roles (e.g.
     `roles/nova-cell/templates/nova.conf.j2:207-216`), and `prechecks` fails while classic queues exist;
   - **the systemd unit text** ([F16](../reference/findings.md#f16)): the 2024.1 template differs from 2023.1's
     (`module_utils/kolla_systemd_worker.py:20-39`) and the whole unit file is compared (`:154-167`), so the first
     2024.1 check of a container whose unit 2023.1 wrote reports drift;
   - **the new `hostnqn` file** of `nova_compute` and `cinder_volume` (`roles/nova-cell/tasks/config.yml:203-216`).

   In addition, every service that `kolla-ansible upgrade` has not reached still runs a 2023.1 image:
   `openstack_release`
   defaults to `2024.1` (`group_vars/all.yml:679-681`) and the check task compares the image
   (`module_utils/kolla_container_worker.py:75`), so a `deploy` or `reconfigure` recreates it on the 2024.1 image
   without
   the role's upgrade tasks. Upgrade first, settle the queue type and list the affected containers ([Pre-execution
   checklist
   §2](../operations/pre-execution-checklist.md#2-first-20241-run-on-a-cloud-deployed-by-20231)).
8. **`deploy` never pulls an image that is already present.** Rebuilt images under the same tag need `pull`
   (`module_utils/kolla_docker_worker.py:365-367`; Podman `module_utils/kolla_podman_worker.py:675-677`). A tag
   change applied with `deploy` recreates the entire fleet at once ([Update container
   images](../operations/update-container-images.md), [F4](../reference/findings.md#f4)) [CODE].
9. **`--limit` does not contain everything.** Delegated tasks still run on `groups[x][0]` controllers (e.g. the
   Neutron DB creation, `roles/neutron/tasks/bootstrap.yml:13-14`), and all hosts' facts are gathered serially by the
   limited hosts (`gather-facts.yml:34-62`) ([Compute scaling](../concepts/compute-scaling-and-performance.md), [Add a
   compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node)) [CODE].
10. **`--list-tasks` cannot predict a run.** Use `genconfig` plus `kolla_set_configs --check`, or staging ([Predict and
    inspect a run](../operations/predict-a-run.md)). kolla's `set_configs.py` is byte-identical to 2023.1's. Three
    things to know about the check [CODE]:
    - **It compares only the files listed in `config.json`**, not its `command` or `permissions`: memcached lists no
      files (`roles/memcached/templates/memcached.json.j2:1-4`), so a change to its command line never shows as
      drift. A plain `reconfigure` still applies it (the changed `config.json` notifies the restart handler), but once
      `genconfig` has written it, no later run restarts the container for it; it takes effect at the next restart for
      another reason ([Write config first, apply in controlled batches
      §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern)).
    - **A newly rendered optional file** whose destination is not yet in the container makes `--check` exit 1 (kolla
      `docker/base/set_configs.py:165-169`), so the container restarts and the file is copied, as in 2023.1 ([Kolla
      images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
    - **It is not the whole check.** `compare_container` also restarts a container whose image, parameters or unit
      text differ (`module_utils/kolla_container_worker.py:58-65`). New in 2024.1, with Podman a container that is not
      running counts as drift and an exit code other than 0 or 1, 137 included, fails the task
      (`module_utils/kolla_podman_worker.py:428-453`) ([Kolla images §3.3](../concepts/kolla-images.md#33-exit-codes)).

## Related

- [Find it fast](find-it-fast.md) — typical operator questions and the section that answers them
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — what to check before a run, and before the first
  2024.1 run on a cloud deployed by 2023.1
- [Risk register](../risk/risk-register.md) — the risks [R1–R30](../risk/risk-register.md#r1), with their precautions
  (R25 does not apply to 2024.1)
- [Technical findings](../reference/findings.md) — the seventeen headline findings, each with its evidence
  ([F16](../reference/findings.md#f16) and [F17](../reference/findings.md#f17) are new in 2024.1)
- [Operations](../operations/index.md) — the operation pages, each with its commands

[readme-03-loop-notify]: ../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code
