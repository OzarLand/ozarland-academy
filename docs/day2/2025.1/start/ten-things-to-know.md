---
title: Ten things to know before a production run
description: Ten things to know before running Kolla-Ansible 2025.1 on production, each with the section that gives the evidence.
tags: [reconfigure, deploy, serial, tags, limit, images, kolla-set-configs, genconfig, handlers, haproxy, rabbitmq, risk]
remember:
  - "<code>reconfigure</code> is <code>deploy</code> for 53 of the 54 roles that have a <code>reconfigure.yml</code>; the only lightweight path is <code>genconfig</code> followed by <code>deploy-containers</code> <span class=\"ev ev-code\">CODE</span>."
  - "Config is applied by a full stop/start through the container's systemd unit, never a reload, and the stop timeout is 60 s, with Docker or Podman <span class=\"ev ev-code\">CODE</span>."
  - "Changed in 2025.1: only the containers that drifted restart, and a service tag no longer restarts HAProxy <span class=\"ev ev-code\">CODE</span>."
  - "Changed in 2025.1: <code>reconfigure</code> and <code>upgrade</code> always run with <code>kolla_serial=0</code>; only <code>deploy -e kolla_serial=N</code> batches a run <span class=\"ev ev-code\">CODE</span>."
  - "<code>deploy</code> never pulls an image that is already present: rebuilt images under the same tag need <code>pull</code> <span class=\"ev ev-code\">CODE</span>."
quiz:
  - q: "What is the only lightweight path to apply config?"
    options: ["<code>reconfigure</code>", "<code>deploy</code> with a service tag", "<code>genconfig</code> followed by <code>deploy-containers</code>"]
    answer: 2
    explain: "<code>reconfigure</code> is <code>deploy</code> for 53 of the 54 roles that have a <code>reconfigure.yml</code> (bifrost is the exception). The only lightweight path is <code>genconfig</code> followed by <code>deploy-containers</code> <span class=\"ev ev-code\">CODE</span>."
  - q: "You run <code>kolla-ansible reconfigure -i multinode -t nova -e kolla_serial=10</code>. How do the handlers restart a changed service?"
    options: ["Ten hosts at a time", "On every host of the play at once", "Only on the first host"]
    answer: 1
    explain: "Changed in 2025.1: <code>reconfigure</code> adds <code>kolla_serial=0</code> after your options, so 0 wins and the handlers restart on every host of the play at once. Use <code>deploy -e kolla_serial=10</code>, which runs the same tasks <span class=\"ev ev-code\">CODE</span>."
  - q: "You run <code>deploy -t keystone</code> after a change that alters the keystone frontend. When does HAProxy load it?"
    options: ["At the end of the same run", "At the next run with <code>-t haproxy</code> or without tags"]
    answer: 1
    explain: "Changed in 2025.1 (F18): the service tag writes the frontend file, but the HAProxy restart comes only from the loadbalancer play's final check, which runs with <code>-t haproxy</code>, <code>-t loadbalancer</code>, <code>-t keepalived</code> or no tag <span class=\"ev ev-code\">CODE</span>."
  - q: "After the move from 2024.1, a <code>reconfigure</code> with no operator change restarts many containers. Which cause does <code>kolla_set_configs --check</code> not show?"
    options: ["A dropped <code>config.json</code> entry", "The changed systemd unit text"]
    answer: 1
    explain: "The unit text is compared by <code>compare_container</code>, not by <code>kolla_set_configs --check</code>; a dropped entry is what the 2025.1 check now reports <span class=\"ev ev-code\">CODE</span>."
---

# Ten things to know before a production run

Ten things to know before running Kolla-Ansible 2025.1 on production. Each item restates a 2025.1 page and links to
the section that gives the evidence; the main citations are repeated here. What a lab run has not confirmed is left
for the community to confirm.

1. **`reconfigure` is `deploy`** for 53 of the 54 roles that have a `reconfigure.yml`; only bifrost keeps its own logic
   (e.g. `roles/nova-cell/tasks/reconfigure.yml:2`). It re-runs Keystone registration, DB creation and the DB-sync
   bootstrap containers for most services, Neutron's included (`roles/neutron/tasks/bootstrap_service.yml:2-21`). The
   only lightweight path is `genconfig` (`kolla_ansible/cli/commands.py:113-125`) followed by `deploy-containers`
   (`kolla_ansible/cli/commands.py:245-256`) ([F5](../reference/findings.md#f5), [Repository architecture
   §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy), [Execution flow
   §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)) [CODE].
2. **Config is applied by a full stop/start, never a reload, and the stop timeout is 60 s.** The container module is
   `kolla_container`, which drives Docker or Podman according to `kolla_container_engine` (default `docker`,
   `group_vars/all.yml:100`; `library/kolla_container.py:411-416`). Containers run under systemd units whose stop is
   `<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:33`), with
   `docker_graceful_timeout: 60` (`group_vars/all.yml:148`); a service still running then is killed
   ([R24](../risk/risk-register.md#r24), [Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)) [CODE]. The
   only signal Kolla sends to a running container is a `SIGHUP` to `nova_scheduler`, which refreshes its cell cache
   (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`). How the Podman path behaves on a real host is
   [NOT AVAILABLE].
3. **Changed in 2025.1: only the containers that drifted restart.** The config tasks no longer notify handlers; the
   shared `service-check-containers` step compares every container of the role and notifies the restart handlers of
   the changed ones only (`roles/service-check-containers/tasks/main.yml:4-41`, the notify at `:34-41`). A nova-compute
   config change no longer restarts `nova_libvirt` and `nova_ssh` with it ([Tags
   §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code), [F1](../reference/findings.md#f1)) [CODE].
4. **Without batching, handlers restart a service on every host of the play at once, and `reconfigure` cannot be
   batched.** Changed in 2025.1: `reconfigure` and `upgrade` put `kolla_serial=0` into their own extra vars, after the
   operator's (`kolla_ansible/cli/commands.py:20-22, :134-136, :276-278`), so `-e kolla_serial=N` has no effect there;
   `ANSIBLE_SERIAL` is no longer read. Use `deploy -e kolla_serial=N`, which runs the same tasks
   ([F19](../reference/findings.md#f19), [R32](../risk/risk-register.md#r32)). MariaDB and RabbitMQ roll by
   themselves: their restarts run in separate plays with `serial: "33%"` (`mariadb.yml:18-52`, `rabbitmq.yml:30-49`;
   one node at a time with three nodes), and each RabbitMQ node is drained first
   (`roles/rabbitmq/tasks/restart_services.yml:10-20`). Every play sets `max_fail_percentage`, 100 by default
   (`site.yml:96-99`): a failed host only drops out, unless every host of a batch fails, which ends the playbook
   (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:202-204`) ([Execution flow
   §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order)) [CODE].
5. **A service tag is never just that service.** For API services it runs Keystone registration and DB sync, and it
   reaches hosts outside the service's own group through delegated steps. It does not run `common` ([Tags
   §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), [Reconfigure a single service
   §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)) [CODE]. Changed in
   2025.1: it writes the service's HAProxy frontend file on every loadbalancer host but no longer restarts HAProxy;
   the restart comes from the loadbalancer play's final check (`site.yml:319-324`), which runs only with `-t haproxy`,
   `-t loadbalancer`, `-t keepalived` or no tag, so the change stays pending until then
   ([F18](../reference/findings.md#f18), [R29](../risk/risk-register.md#r29)). `--skip-tags haproxy` keeps the
   frontend file untouched ([Reconfigure a single service
   §1.2](../operations/reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)).
6. **`-t common` does the work, and only it does.** `common` is its own play, tagged `common` (`site.yml:88-103`), so
   fluentd, cron and kolla_toolbox changes need `-t common` or a run without tags; a service tag leaves them pending
   ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code), [Apply `common`
   changes](../operations/apply-common-changes.md)) [CODE]. Changed in 2025.1: the common config step no longer pulls
   the fluentd image.
7. **Global settings land in per-host files, and the first 2025.1 run changes some of them everywhere.** `enable_*`,
   RabbitMQ/memcached membership and passwords end up in compute-side configs, so small central changes cause
   fleet-wide restarts ([F6](../reference/findings.md#f6), [Why a small change creates a large
   workload](../risk/small-change-large-workload.md)). On a cloud deployed by 2024.1, code changes restart containers
   whose operator config did not change ([Predict and inspect a run
   §2](../operations/predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241)) [CODE]:
   - **the systemd unit text** ([F16](../reference/findings.md#f16)): the 2025.1 template adds `PartOf=kolla.target`
     (`module_utils/kolla_systemd_worker.py:27`) and the whole unit file is compared (`:155-168`), so the first 2025.1
     check of a container whose unit 2024.1 wrote reports drift;
   - **the default ulimits**, with Docker outside the Red Hat family (`group_vars/all.yml:201-224`);
   - **quorum queues only** ([F17](../reference/findings.md#f17)): classic queues must be migrated before the run
     ([R27](../risk/risk-register.md#r27));
   - **with OVN, the Southbound relays**, on by default, which move the chassis ([R33](../risk/risk-register.md#r33)).

   In addition, every service that `kolla-ansible upgrade` has not reached still runs a 2024.1 image:
   `openstack_release` defaults to `2025.1` (`group_vars/all.yml:795`), so a `deploy` or `reconfigure` recreates it on
   the 2025.1 image without the role's upgrade tasks. Upgrade first, migrate the queues and list the affected
   containers ([Pre-execution checklist
   §2](../operations/pre-execution-checklist.md#2-first-20251-run-on-a-cloud-deployed-by-20241)).
8. **`deploy` never pulls an image that is already present.** Rebuilt images under the same tag need `pull`
   (`module_utils/kolla_docker_worker.py:376-378`; Podman `module_utils/kolla_podman_worker.py:789-791`). A tag
   change applied with `deploy` recreates the entire fleet at once ([Update container
   images](../operations/update-container-images.md), [F4](../reference/findings.md#f4)) [CODE].
9. **`--limit` does not contain everything.** Delegated tasks still run on `groups[x][0]` controllers (e.g. the
   Neutron DB creation, `roles/neutron/tasks/bootstrap.yml:13-14`), and the facts of `kolla_ansible_delegate_facts_hosts`
   (all hosts by default) are gathered serially by the limited hosts (`gather-facts.yml:34-62`)
   ([F8](../reference/findings.md#f8), [F9](../reference/findings.md#f9), [Compute
   scaling](../concepts/compute-scaling-and-performance.md), [Add a compute node
   §2](../operations/add-a-compute-node.md#2-add-a-compute-node)) [CODE].
10. **`--list-tasks` cannot predict a run.** Use `genconfig` plus `kolla_set_configs --check`, or staging ([Predict and
    inspect a run](../operations/predict-a-run.md)). Three things to know about the 2025.1 check [CODE]
    ([F14](../reference/findings.md#f14)):
    - **It now compares the command too.** kolla's `set_configs.py` reports a difference when the running command
      differs from the `command` of `config.json`, so memcached's settings, all in its command, are now detected; a
      change confined to `permissions` is still not.
    - **A dropped entry never stops firing.** Once an entry is removed from `config.json`, the check reports drift on
      every run until the container is recreated ([F21](../reference/findings.md#f21)).
    - **It is not the whole check.** `compare_container` also restarts a container whose image, parameters or unit
      text differ (`module_utils/kolla_container_worker.py:58-65`). With Podman a container that is not running counts
      as drift and an exit code other than 0 or 1, 137 included, fails the task
      (`module_utils/kolla_podman_worker.py:524-555`) ([Kolla images §3.3](../concepts/kolla-images.md#33-exit-codes)).

## Related

- [Find it fast](find-it-fast.md) — typical operator questions and the section that answers them
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — what to check before a run, and before the first
  2025.1 run on a cloud deployed by 2024.1
- [Risk register](../risk/risk-register.md) — the risks [R1–R33](../risk/risk-register.md#r1), with their precautions
- [Technical findings](../reference/findings.md) — the headline findings, each with its evidence
  ([F18](../reference/findings.md#f18) to [F22](../reference/findings.md#f22) are new in 2025.1)
- [Operations](../operations/index.md) — the operation pages, each with its commands
- [Ten things to know (2024.1)](../../2024.1/start/ten-things-to-know/) — the same page for the previous release
