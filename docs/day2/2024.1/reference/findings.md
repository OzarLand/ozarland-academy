---
title: Technical findings
description: The headline findings of the source study, F1 to F17, re-checked against 2024.1-eom, each with its 2024.1 status, evidence and why it matters.
tags: [evidence, loop-notify, tags, limit, serial, images, kolla-set-configs, one-shot, reconfigure, nova, neutron, docker, podman, systemd, rabbitmq]
remember:
  - "Restart blast radius is still per role-on-host, not per container: a nova-compute-only change restarts <code>nova_libvirt</code> and <code>nova_ssh</code> too (ansible-core 2.16.20). <span class=\"ev ev-code\">CODE</span>"
  - "Same-tag image rebuilds are not picked up by <code>deploy</code>/<code>reconfigure</code>/<code>upgrade</code>, with Docker or Podman: only absent images are pulled; an explicit <code>pull</code> is required. <span class=\"ev ev-code\">CODE</span>"
  - "A <code>reconfigure</code> is a <code>deploy</code> (52 of the 54 roles that have one): it applies schema migrations if the image tag moved, Neutron included. <span class=\"ev ev-code\">CODE</span>"
  - "New in 2024.1: the systemd unit template changed, so the first 2024.1 check of a container whose unit was written by 2023.1 (and not yet rewritten by a 2024.1 create, recreate or restart) reports drift and the handler restarts it; Swift has no such check. <span class=\"ev ev-code\">CODE</span>"
  - "New in 2024.1: RabbitMQ quorum queues are on by default; a cloud that kept the 2023.1 default gets <code>rabbit_quorum_queue = true</code> in its service configs, and <code>prechecks</code> fails while classic queues exist. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "In 2024.1, a config change touches one nova-compute container only. Which containers of that host can restart?"
    options: ["Every container of that role on that host: a nova-compute-only change restarts <code>nova_libvirt</code> and <code>nova_ssh</code> too", "Only the container whose config changed"]
    answer: 0
    explain: "Loop-notify amplification still holds in 2024.1 <span class=\"ev ev-code\">CODE</span>: in ansible-core 2.16.20 a looped task is changed when any item changed, and then the handlers named by every executed item are notified. Restart blast radius is per role-on-host, not per container."
    see: "f1--loop-notify-amplification"
  - q: "In 2024.1, what does <code>-t common</code> do?"
    options: ["Nothing: it is a no-op, because tags on the dynamic <code>include_tasks</code> do not propagate", "It renders the common configs and restarts what changed"]
    answer: 1
    explain: "F2 no longer holds in 2024.1 <span class=\"ev ev-code\">CODE</span>: <code>common</code> is a play of its own with play-level <code>tags: common</code>, and the included tasks inherit the play tag, so <code>-t common</code> renders the common configs and restarts what changed. A service tag (e.g. <code>-t nova</code>) skips it."
    see: "f2---t-common-is-a-no-op"
  - q: "You upgraded a Docker-based cloud from 2023.1 to 2024.1. A container was left out of the upgrade, so no 2024.1 run has recreated or restarted it. What happens at its next 2024.1 <code>deploy</code> or <code>reconfigure</code>, with no other change?"
    options: ["Nothing: its config and image are unchanged", "Its check reports drift because the unit file text differs from the 2024.1 template; the handler rewrites the unit and restarts the container"]
    answer: 1
    explain: "F16 <span class=\"ev ev-code\">CODE</span>: <code>compare_container</code> includes <code>check_unit_change</code>, which compares the whole unit file text, and the 2024.1 template writes <code>StartLimitInterval=</code> where 2023.1 wrote <code>StartLimitIntervalSec=</code> followed by a blank line."
    see: "f16--the-first-20241-check-restarts-a-container-whose-unit-20231-wrote"
  - q: "A 2023.1 cloud never set <code>om_enable_rabbitmq_quorum_queues</code> and still uses classic queues. What does <code>kolla-ansible prechecks</code> do with the 2024.1 defaults?"
    options: ["It passes: the 2024.1 default is still classic queues", "It fails: the default is now quorum queues, and the precheck asserts that every queue except <code>reply_</code> and <code>_fanout</code> ones is a quorum queue"]
    answer: 1
    explain: "F17 <span class=\"ev ev-code\">CODE</span>: <code>om_enable_rabbitmq_quorum_queues</code> now defaults to <code>true</code>, and the RabbitMQ precheck lists the queues and asserts their type when a <code>rabbitmq</code> container exists. Turning both quorum and HA off fails another precheck."
    see: "f17--rabbitmq-quorum-queues-are-on-by-default"
---

# Technical findings

The study consolidates three things. This page holds the first:

1. what was established and how (evidence level): the headline findings below;
2. implementation limitations and bugs found in `2024.1-eom`: [Known bugs and
   limitations](../troubleshooting/known-bugs-and-limitations.md);
3. what the sources do not establish: [Open questions](../troubleshooting/open-questions.md) and [What is not
   known](../troubleshooting/what-is-not-known.md).

> [!NOTE]
> **Key answers**
>
> - **Fifteen headline findings ([F1–F15](#f1))**, first established on `ussuri-eol`, re-checked against `2023.1-eol`
>   and now against `2024.1-eom`, each with its 2024.1 evidence and why it matters, plus **two new 2024.1 findings**
>   ([F16](#f16), [F17](#f17)) ([Headline findings](#headline-findings)).
> - **Still hold in 2024.1:** loop-notify amplification ([F1](#f1), re-read in ansible-core 2.16.20), same-tag image
>   rebuilds ([F4](#f4), now for Docker and Podman), `reconfigure` = `deploy` ([F5](#f5)), [F6](#f6) to [F10](#f10)
>   (F7, F9 and F10 re-read in ansible-core 2.16.20), [F12](#f12), [F13](#f13), the `kolla_set_configs --check` blind
>   spots ([F14](#f14), same kolla script; Podman handles exit codes differently) and per-image bootstrap behaviour
>   ([F15](#f15)).
> - **Still no longer hold in 2024.1:** the `-t common` no-op ([F2](#f2)), the ignored stop timeout ([F3](#f3): the
>   60 s `docker_graceful_timeout` reaches `<engine> stop` through the systemd unit) and the `ml2_conf.ini` merge into
>   `openvswitch_agent.ini` ([F11](#f11)).
> - **New in 2024.1:** the changed systemd unit template makes the first 2024.1 check restart every checked container
>   whose unit was written by 2023.1 and not yet rewritten by a 2024.1 run ([F16](#f16)); RabbitMQ quorum queues are on
> by default, which changes every service's
>   messaging config and fails `prechecks` while classic queues exist ([F17](#f17)).

Evidence levels: **[CODE]** and **[NOT AVAILABLE]**, defined once, in [Evidence
labels](../start/conventions.md#evidence-labels). The study rests only on reading source code; no run against a host is
used as evidence. Paths are relative to the kolla-ansible `2024.1-eom` checkout (commit `890396f`); paths prefixed
`kolla` point into the kolla image repository (`2024.1-eom`, commit `ed7a36a`), and `ansible-core 2.16.20` into the
Ansible source.

## Headline findings

| # | Finding |
|---|---|
| [F1](#f1) | Loop-notify amplification |
| [F2](#f2) | `-t common` is a no-op (no longer holds in 2024.1) |
| [F3](#f3) | `docker_graceful_timeout` and `docker_client_timeout` are ignored (no longer holds in 2024.1) |
| [F4](#f4) | Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade` |
| [F5](#f5) | `reconfigure` = `deploy` |
| [F6](#f6) | Global inputs are rendered into per-host files |
| [F7](#f7) | `--list-tasks` cannot show what a tag runs |
| [F8](#f8) | `--limit` does not confine actions |
| [F9](#f9) | With `--limit`, all hosts' facts are gathered sequentially |
| [F10](#f10) | `kolla_serial` makes `run_once` steps repeat per batch |
| [F11](#f11) | The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides (no longer holds in 2024.1) |
| [F12](#f12) | The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes` |
| [F13](#f13) | The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes |
| [F14](#f14) | `kolla_set_configs --check` has blind spots |
| [F15](#f15) | What the bootstrap containers run differs per image |
| [F16](#f16) | The first 2024.1 check restarts a container whose unit 2023.1 wrote (new in 2024.1) |
| [F17](#f17) | RabbitMQ quorum queues are on by default (new in 2024.1) |

<a id="f1"></a>

### F1 — Loop-notify amplification

**Still holds in 2024.1** [CODE], re-read in ansible-core 2.16.20.

| | |
|---|---|
| **Finding** | **Loop-notify amplification.** When a config/check task loops over a role's services and *one* item changes, ansible-core 2.16.20 notifies the handlers of *all* executed items. In Kolla this means a change for one container restarts every container of that role on that host. A nova-compute-only change restarts `nova_libvirt` and `nova_ssh`; a scheduler-only change restarts `nova_api`; a change on a network node restarts all neutron agents there |
| **Evidence** | [CODE] ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:124-130` (the loop result is changed when any item changed), `:819-820` (every executed item carries `_ansible_notify`; an item whose `when` is false returns earlier, `:483-484`), `lib/ansible/plugins/strategy/__init__.py:648-661` (for each item result that carries `_ansible_notify`, the handlers are notified when the *whole* task result is changed); `roles/nova-cell/tasks/check-containers.yml:2-22`, `roles/nova/tasks/config.yml:64-82`, `roles/neutron/tasks/check-containers.yml:2-19` (each loops over the role's services with `notify: "Restart {{ item.key }} container"`); the compute-host items are `nova-libvirt`, `nova-ssh` and `nova-compute` (`roles/nova-cell/defaults/main.yml:3-6,14-18,53-60`; `group_vars/all.yml:827,829,863`); walk-through in [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| **Why it matters** | Restart blast radius is per *role-on-host*, not per container. libvirt restarts far more often than operators expect |

<a id="f2"></a>

### F2 — `-t common` is a no-op

**No longer holds in 2024.1** [CODE], as in 2023.1. `common` is a play of its own, with play-level `tags: common`
(`site.yml:88-103`), and no role has a `meta/` directory, so nothing else reaches the role. The included tasks inherit
the play tag, so `-t common` renders the common configs and restarts what changed.

| | |
|---|---|
| **Finding** | **Ussuri:** `-t common` was a no-op, because tags on the dynamic `include_tasks` do not propagate to the included tasks. **2024.1:** `roles/common/tasks/main.yml:1-2` is a bare `include_tasks: "{{ kolla_action }}.yml"`, reached only from the `Apply role common` play; `-t common` runs it on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` hosts, and a service tag (e.g. `-t nova`) skips it. New in 2024.1, the common `config.yml` also makes sure the fluentd image is present (`ensure_image`, which pulls only an absent image) and reads its labels before rendering (`roles/common/tasks/config.yml:42-91`), so `-t common` and `genconfig` can pull that image |
| **Evidence** | [CODE] `site.yml:88-103`; `roles/common/tasks/main.yml:1-2`; ansible-core 2.16.20 `lib/ansible/playbook/taggable.py:42` (`tags` is an extending attribute), `lib/ansible/playbook/block.py:294-361` (a block's value extends its parent's, role's and play's, `:352-361` for the play), `lib/ansible/plugins/strategy/linear.py:272` (included blocks are filtered by tag) ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code); [R25](../risk/risk-register.md#r25); [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard)) |
| **Why it matters** | `common` changes (fluentd/cron/toolbox) are applied by `-t common` or by an untagged run, and never by a service-tagged run: a fluentd/logrotate change made when enabling a service with `-t <svc> deploy` waits for the next run of the common play ([R2](../risk/risk-register.md#r2)) |

<a id="f3"></a>

### F3 — `docker_graceful_timeout` and `docker_client_timeout` are ignored

**No longer holds in 2024.1** [CODE], as in 2023.1. The module that replaced `kolla_docker`, `kolla_container`, still
declares the two options without an argument default, so the values from `docker_common_options` are used; containers
(except one-shots) run under a systemd unit whose `ExecStop` carries the graceful timeout, now for Docker and Podman
([R24](../risk/risk-register.md#r24)).

| | |
|---|---|
| **Finding** | **Ussuri:** the `kolla_docker` argument defaults (10 s, 120 s) overrode `common_options`, so every stop sent SIGKILL 10 s after SIGTERM. **2024.1:** `graceful_timeout` and `client_timeout` are declared without a default, so the `common_options` values (`docker_graceful_timeout: 60`, `docker_client_timeout: 120`) are taken; the 10 s and 120 s values apply only when neither is given. A restart or stop of a long-running container goes through the unit `kolla-<name>-container.service`, whose `ExecStop` is now `/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`docker` or `podman`). Without a unit file the Docker worker calls the engine's `stop` with the same timeout; the Podman worker does so for a one-shot container, and also gives the timeout to the container as `stop_timeout` |
| **Evidence** | [CODE] `library/kolla_container.py:313,335` (no default), `:361-393` (common-options merge, fallback 10/120 at `:370-371`); `group_vars/all.yml:105,139,142-153`; `module_utils/kolla_systemd_worker.py:20-39,50-54,69-79`; `module_utils/kolla_docker_worker.py:415-431,439-459`; `module_utils/kolla_podman_worker.py:124-125,575-593,602-617` |
| **Why it matters** | A service still running 60 s after SIGTERM is killed with its in-flight work (heat-engine, cinder copies, glance uploads); raising `docker_graceful_timeout` has an effect (it reaches the unit on the next restart, [R24](../risk/risk-register.md#r24), and changing it changes the unit text, which `compare_container` detects, [F16](#f16)). For `nova_libvirt` this matters only if libvirtd has not exited by then ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)). [NOT AVAILABLE] systemd's own stop timeout for these units (the unit sets none). [NOT AVAILABLE] Whether services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`) receive SIGTERM at all ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)) |

<a id="f4"></a>

### F4 — Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`

**Still holds in 2024.1** [CODE], for the Docker worker and for the new Podman worker.

| | |
|---|---|
| **Finding** | **Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`.** Only absent images are pulled; an explicit `pull` is required |
| **Evidence** | [CODE] Docker: `module_utils/kolla_docker_worker.py:107-122` (the container's image id is compared with the local image of that tag), `:353-358` and `:365-367` (`check_image`, then `pull_image` only when the image is absent), `:501-503` (`ensure_image`, same rule). Podman: `module_utils/kolla_podman_worker.py:317-335` (same comparison), `:526-527` and `:675-677` (`ensure_image` pulls only an absent image) ([R13](../risk/risk-register.md#r13)) |
| **Why it matters** | Mutable tags create silent drift between hosts. A later unrelated `pull` turns into a mass recreate |

<a id="f5"></a>

### F5 — `reconfigure` = `deploy`

**Still holds in 2024.1** [CODE], without the Neutron exception (gone since 2023.1).

| | |
|---|---|
| **Finding** | **`reconfigure` = `deploy`** for 52 of the 54 roles that have a `tasks/reconfigure.yml` (51 via `import_tasks: deploy.yml`, plus skyline via `include_tasks: deploy.yml`; only swift and bifrost have their own logic). A reconfigure re-runs Keystone registration, DB creation/grants and the DB-sync bootstrap containers of the services. `bootstrap_neutron` is imported without any condition and runs on every `deploy` and `reconfigure`; `neutron_enable_rolling_upgrade` is read only by `upgrade.yml` |
| **Evidence** | [CODE] `roles/*/tasks/reconfigure.yml` (e.g. `roles/skyline/tasks/reconfigure.yml:2`); `roles/neutron/tasks/bootstrap.yml:38`, `roles/neutron/tasks/bootstrap_service.yml:2-21`, `roles/neutron/tasks/upgrade.yml:4-8`, `roles/neutron/defaults/main.yml:732` ([Repository architecture §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). One-shot containers counted from the code: `-t nova` starts 6 on `control01` when cell0 is mapped and the cell is unchanged (API DB sync, `map_cell0`, `list_cells` ×3 — the cell0 lookup, `create_cells` and `discover_computes` —, cell DB sync: `nova.yml:49-55`, `roles/nova/tasks/bootstrap.yml:54-56`, `roles/nova/tasks/map_cell0.yml:2-30,63-67`, `roles/nova-cell/tasks/bootstrap.yml:41-43`, `create_cells.yml:2-4`, `discover_computes.yml:4-5,21`, `get_cell_settings.yml:2-21`); on `-t neutron reconfigure` the neutron role starts one, `bootstrap_neutron`, on the first `neutron-server` host (`roles/neutron/tasks/bootstrap_service.yml:20-21`). [NOT AVAILABLE] Totals for a run without a tag, which depend on the enabled services |
| **Why it matters** | A "reconfigure" applies schema migrations if the image tag moved, for Neutron too (`neutron-db-manage … upgrade head` for neutron and each enabled subproject, kolla `docker/neutron/neutron-server/extend_start.sh:5-13`). There is never a "config only" path except `genconfig` + `deploy-containers` (`tools/kolla-ansible:499-501,557-559`) |

<a id="f6"></a>

### F6 — Global inputs are rendered into per-host files

**Still holds in 2024.1** [CODE].

| | |
|---|---|
| **Finding** | **Global inputs are rendered into per-host files.** `enable_*` flags, RabbitMQ/memcached membership, service passwords, the oslo.messaging options and the external FQDN end up in compute-side files |
| **Evidence** | [CODE] `group_vars/all.yml:248,258` (`rpc_transport_url`, `notify_transport_url`: every RabbitMQ host, user and password); `roles/nova-cell/templates/nova.conf.j2:37,57,184,207-216` (transport URLs, console base URL from the public FQDN, quorum-queue options, [F17](#f17)); `roles/neutron/templates/neutron.conf.j2:123` (memcached list), rendered for the OVS agent on computes too (`roles/neutron/tasks/config.yml:87-122`); `roles/common/tasks/config.yml:140-270` (`td-agent.conf` and `logrotate.conf` from the global `enable_*` flags) |
| **Why it matters** | Small central changes cause fleet-wide restarts |

<a id="f7"></a>

### F7 — `--list-tasks` cannot show what a tag runs

**Still holds in 2024.1** [CODE], re-read in ansible-core 2.16.20 and seen in its own listing.

| | |
|---|---|
| **Finding** | **`--list-tasks` cannot show what a tag runs**, and `--list-hosts` shows 0 hosts for `&enable_*` plays |
| **Evidence** | [CODE] ansible-core 2.16.20 `lib/ansible/cli/playbook.py:179-183` (host patterns are resolved before any task runs), `:214-219` (the listing walks the statically compiled play, where a dynamic include is one task), `lib/ansible/inventory/manager.py:447-449` (an `&` pattern intersects with a group that does not exist yet); `site.yml:15-74` (the `enable_*` groups are created by `group_by` at run time); [list-tasks-nova.txt](listings/list-tasks-nova.txt) (ansible-core 2.16.20 output on the 2024.1 tree: one `include_tasks` line per nova play, and `Could not match supplied host pattern` warnings for the `enable_*` groups) |
| **Why it matters** | Operators need `genconfig` or staging to predict a run |

<a id="f8"></a>

### F8 — `--limit` does not confine actions

**Still holds in 2024.1** [CODE].

| | |
|---|---|
| **Finding** | **`--limit` does not confine actions.** `delegate_to: groups[x][0]` runs work on hosts outside the limit. With `deploy --limit` set to a compute host, `control01` (the first `neutron-server` and `nova-conductor` host of the `multinode` inventory) runs the Neutron DB create/grant and the `bootstrap_neutron` container, plus cell discovery (`nova_list_cells`, `openstack compute service list`, `nova-manage cell_v2 discover_hosts`). The nova-cell RabbitMQ user/vhost creation is also delegated (to the first RabbitMQ host), but it runs only when the first nova-conductor is inside the limit, so a limit to compute hosts does not run it |
| **Evidence** | [CODE] `site.yml:671-693` and `nova.yml:125-147` (both plays include `compute`); `roles/neutron/tasks/bootstrap.yml:13-14,33-34`, `roles/neutron/tasks/bootstrap_service.yml:20-21`; `roles/nova-cell/tasks/deploy.yml:19-37`, `wait_discover_computes.yml:8-43,87-90`, `discover_computes.yml:4-23`, `get_cell_settings.yml:2-21`; `roles/nova-cell/tasks/rabbitmq.yml:10-12`; `inventory/multinode:3-5,90-91,99-100,230-231,252-253` ([Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node)) |
| **Why it matters** | "Only the new compute" still executes DB-sync containers on a controller |

<a id="f9"></a>

### F9 — With `--limit`, all hosts' facts are gathered sequentially

**Still holds in 2024.1** [CODE], re-read in ansible-core 2.16.20.

| | |
|---|---|
| **Finding** | **With `--limit`, all hosts' facts are gathered sequentially** by the limited hosts (delegated loop) |
| **Evidence** | [CODE] `gather-facts.yml:34-62` (each limited host loops over its share of `groups['all']`; skipped for hosts in the limit and for hosts that already have facts, `:59-61`); loop items run one after another in the same worker (ansible-core 2.16.20 `lib/ansible/executor/task_executor.py:288-390`, each item through `_execute` at `:336`) ([R23](../risk/risk-register.md#r23)) |
| **Why it matters** | O(total hosts) serial latency on every limited run without fact caching |

<a id="f10"></a>

### F10 — `kolla_serial` makes `run_once` steps repeat per batch

**Still holds in 2024.1** [CODE], re-read in ansible-core 2.16.20.

| | |
|---|---|
| **Finding** | **`kolla_serial` makes `run_once` steps repeat per batch** (API DB sync ×3 with serial 1 and the three controllers of the `multinode` inventory) and orders a play's restarts by host-pattern order (computes before conductors in the nova-cell play) |
| **Evidence** | [CODE] ansible-core 2.16.20 `lib/ansible/executor/playbook_executor.py:181-190` (one strategy run per batch, with the inventory restricted to the batch), `:274-281` (batches follow the play's host order), `lib/ansible/plugins/strategy/linear.py:181,207-209` (a `run_once` task is queued for the first host left, then the host loop stops), `lib/ansible/inventory/manager.py:401-411,429-453` (restriction to the batch; hosts kept in pattern order); `roles/nova/tasks/bootstrap_service.yml:2-21`; `nova.yml:29-55,125-147`; `inventory/multinode:3-7,99-100,227-228` ([Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)) |
| **Why it matters** | Batching reduces blast radius but multiplies bootstrap work, and exposes ordering within a play |

<a id="f11"></a>

### F11 — The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides

**No longer holds in 2024.1** [CODE], as in 2023.1. `ml2_conf.ini` is rendered only for `neutron-server` and
`neutron-infoblox-ipam-agent`; `openvswitch_agent.ini` has its own template and override files
([R5](../risk/risk-register.md#r5)).

| | |
|---|---|
| **Finding** | **Ussuri:** the `openvswitch_agent.ini` merge included the operator's `ml2_conf.ini` overrides. **2024.1:** `openvswitch_agent.ini` merges `templates/openvswitch_agent.ini.j2` with `neutron/openvswitch_agent.ini` and `neutron/<host>/openvswitch_agent.ini` only |
| **Evidence** | [CODE] `roles/neutron/tasks/config.yml:159-179` (`services_need_ml2_conf_ini`), `:198-213` (`openvswitch_agent.ini`); `roles/neutron/tasks/deploy.yml:11-23` (config, then `check-containers.yml`, then `Flush Handlers`); `roles/neutron/tasks/check-containers.yml:2-19` |
| **Why it matters** | Server-side ML2 changes do not restart every OVS agent; they restart `neutron_server`, and through loop-notify every neutron container on a host that also runs neutron-server ([F1](#f1), [R5](../risk/risk-register.md#r5)). OVS agent options belong in `neutron/openvswitch_agent.ini` |

<a id="f12"></a>

### F12 — The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes`

**Still holds in 2024.1** [CODE].

| | |
|---|---|
| **Finding** | **The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start** when `enable_neutron_agent_ha: yes` (default `no`); its comment says this removes all L3 namespaces (what the command does is neutron code: [NOT AVAILABLE]). New in 2024.1, the cleanup also reads `fwaas_driver.ini` when FWaaS is enabled |
| **Evidence** | [CODE] `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-14`; `group_vars/all.yml:816` |
| **Why it matters** | [NOT AVAILABLE] Whether an L3 agent restart interrupts router traffic on that node ([Q4](../troubleshooting/open-questions.md#q4)). `neutron_l3_agent_failover_delay` (default `0`, `roles/neutron/defaults/main.yml:651`) spaces the restarts of running L3 agents across hosts when set above `0`; with the default they are not spaced (`roles/neutron/handlers/main.yml:127-157`) ([R6](../risk/risk-register.md#r6)) |

<a id="f13"></a>

### F13 — The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes

**Still holds in 2024.1** [CODE].

| | |
|---|---|
| **Finding** | **The Nova deploy order** puts nova-compute before OVS and the Neutron agents on new computes |
| **Evidence** | [CODE] `site.yml:609` (`import_playbook: nova.yml`, whose `Apply role nova-cell` play is `nova.yml:125-147`), then `site.yml:611-624` (`Apply role openvswitch`) and `site.yml:671-693` (`Apply role neutron`) |
| **Why it matters** | [NOT AVAILABLE] Whether instances can be scheduled on such a compute before the later plays finish ([Execution flow §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)); relevant when adding computes one by one |

<a id="f14"></a>

### F14 — `kolla_set_configs --check` has blind spots

**Still holds in 2024.1** [CODE]: kolla's `docker/base/set_configs.py` is byte-identical to 2023.1's. With Podman,
the module reads the exit codes differently.

| | |
|---|---|
| **Finding** | **`kolla_set_configs --check` has blind spots.** It compares only the `config_files` entries of `config.json` (content, mode, owner). A change confined to `config.json` itself (`command`, `permissions`; all of memcached's settings) is never detected, nor is an entry dropped from `config.json`. A newly added optional file reports drift (exit 1), like any missing destination. `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run. A restart removes (or resets to the original) the destination of a dropped entry when it was recorded at the container's first start; glob sources are never recorded and keep their stale files. **New in 2024.1, with `kolla_container_engine: podman`:** a container that is not `running` counts as drift before any check, and an exit code other than 0 or 1 (137 included) fails the task, where the Docker worker treats 137 as drift |
| **Evidence** | [CODE] kolla `docker/base/set_configs.py:64-72,165-198,200-218,220-242,452-474,502,516-532,556-559,562-582`; `module_utils/kolla_docker_worker.py:146-181`; `module_utils/kolla_podman_worker.py:428-453`; `roles/memcached/templates/memcached.json.j2:2-3` ([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)) |
| **Why it matters** | "`genconfig` + `--check`" ([Predict and inspect a run](../operations/predict-a-run.md)) under-reports some changes and over-reports others. A `config.json`-only change is applied by a normal deploy/reconfigure, because the changed template task notifies the restart handler. Once `genconfig` has written it, neither `deploy-containers` nor a later run (its template task is then unchanged) applies it until the container restarts for another reason |

<a id="f15"></a>

### F15 — What the bootstrap containers run differs per image

**Still holds in 2024.1** [CODE]: the five kolla start scripts are unchanged from 2023.1.

| | |
|---|---|
| **Finding** | **What the bootstrap containers run differs per image.** Nova's bootstrap containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`). Placement's `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure. Heat's does not re-apply a changed `heat_domain_admin_password` to Keystone (it creates the domain user only when `heat_user_domain` is missing). neutron-server's migrates neutron and each enabled subproject; the bootstrap and the rolling `upgrade` use the same list, the enabled `neutron_subprojects` (in 2024.1 including `tap-as-a-service`) |
| **Evidence** | [CODE] kolla `docker/nova/nova-api/extend_start.sh:9-30`, `docker/nova/nova-conductor/extend_start.sh:3-17`, `docker/placement/placement-api/extend_start.sh:5-9`, `docker/heat/heat-api/extend_start.sh:5-17`, `docker/neutron/neutron-server/extend_start.sh:5-13,17-34`; `roles/nova/tasks/bootstrap_service.yml:11`, `roles/nova-cell/tasks/bootstrap_service.yml:11`, `roles/placement/tasks/bootstrap_service.yml:11`, `roles/heat/tasks/bootstrap_service.yml:11,22`, `roles/neutron/defaults/main.yml:674-686,727,733` |
| **Why it matters** | What a "reconfigure" or a tag-changing "deploy" does to databases depends on the image, not only on kolla-ansible ([Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)) |

<a id="f16"></a>

### F16 — The first 2024.1 check restarts a container whose unit 2023.1 wrote

**New in 2024.1** [CODE].

| | |
|---|---|
| **Finding** | **The systemd unit template changed, and the unit text is part of the container check.** The 2024.1 template writes `StartLimitInterval=` where 2023.1 wrote `StartLimitIntervalSec=` followed by a blank line; it also names the engine in `Description`, `After`/`Wants`, `ExecStart` and `ExecStop`, but with Docker those lines render as the 2023.1 template wrote them (it hard-coded `docker`), so the start-limit line alone makes a 2023.1 unit differ. `compare_container` reports drift when `check_unit_change` finds that the unit file on disk differs from the rendered template, whole text compared. So, with Docker, the first 2024.1 `Check <role> containers` task that runs for a container whose unit was written by 2023.1 code reports it as changed, even when nothing else differs; the restart handler then restarts it (`COPY_ALWAYS`: `restart_container`, which rewrites the unit, reloads systemd and enables it before restarting the unit). A container that a 2024.1 run creates, recreates or restarts (an upgrade that reaches its role does one of these) gets the new unit then and is not flagged again. One-shot containers have no unit. Swift has no check task: its `deploy` uses `start_container`, which does not compare the unit |
| **Evidence** | [CODE] `module_utils/kolla_systemd_worker.py:20-39` (template), `:50-54` (engine dependency), `:154-167` (`check_unit_change`: whole text), `:172-185` (`create_unit_file`: write, reload, enable); `module_utils/kolla_container_worker.py:58-65` (`compare_container`, Docker); `module_utils/kolla_podman_worker.py:294-301` (same for Podman); `module_utils/kolla_docker_worker.py:334-339` (unit written at creation, none for a one-shot), `:341-363` (`recreate_or_restart_container`), `:365-389` (`start_container`), `:439-459` (`restart_container`); e.g. `roles/nova-cell/tasks/check-containers.yml:2-22`; `roles/swift/tasks/deploy.yml:1-10`; 2023.1 template: 2023.1 kolla-ansible tree, ansible/module_utils/kolla_systemd_worker.py, lines 20-40 ([Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)) |
| **Why it matters** | After an upgrade from 2023.1, a `deploy`/`reconfigure` that the operator expects to be a no-op restarts every checked container whose unit no 2024.1 run has rewritten yet (for example a role left out of a tagged or `--limit` upgrade), on every host it runs on, and through loop-notify the rest of its role on that host ([F1](#f1)). Any later change of `docker_graceful_timeout`, `docker_client_timeout`, `docker_restart_policy_retry`, or of `docker_restart_policy` to a value that renders differently (`unless-stopped` and `always` both render `Restart=always`, `kolla_systemd_worker.py:56-58`), changes the unit text too, and restarts every long-running container whose role runs a check task at the next check. [NOT AVAILABLE] Whether systemd treats the two start-limit key names the same ([Kolla images §2.3](../concepts/kolla-images.md#23-kolla_set_configs-copy-and-permissions)) |

<a id="f17"></a>

### F17 — RabbitMQ quorum queues are on by default

**New in 2024.1** [CODE].

| | |
|---|---|
| **Finding** | **`om_enable_rabbitmq_quorum_queues` defaults to `true`** (2023.1: `false`). Every service template that renders `[oslo_messaging_rabbit]` then writes `rabbit_quorum_queue = true` (26 templates in 24 roles, e.g. nova, nova-cell, neutron, cinder, glance, keystone), so a cloud that kept the 2023.1 default gets a changed config file, and a restart, for those services on its first 2024.1 run that renders configs, computes included (neutron's `neutron.conf`, nova-cell's `nova.conf`). `kolla-ansible prechecks` is stricter: it fails when HA and quorum are **equal**, so also when both are off (2023.1 failed only when both were on); and when a `rabbitmq` container exists and quorum is on, it lists the queues and asserts that every queue except `reply_` and `_fanout` ones is a quorum queue, so it fails while classic queues exist |
| **Evidence** | [CODE] `group_vars/all.yml:266-279`; `roles/nova-cell/templates/nova.conf.j2:207-216`, `roles/nova/templates/nova.conf.j2:156-163`, `roles/neutron/templates/neutron.conf.j2:146-153`; `roles/prechecks/tasks/service_checks.yml:67-81`; `roles/rabbitmq/tasks/precheck.yml:8-15,131-152,185-189`; `site.yml:77-86` (the prechecks play runs only for `kolla_action` `precheck`) |
| **Why it matters** | Keeping classic queues needs an explicit choice, and the only choice that passes `prechecks` is `om_enable_rabbitmq_high_availability: true` with the `ha-all` mirroring policy in place (`roles/rabbitmq/tasks/precheck.yml:107-129`); otherwise the queues have to be migrated to quorum queues, a procedure the precheck message calls manual. On a cloud that kept the 2023.1 default (HA off), 2023.1 runs removed `ha-all` (2023.1 kolla-ansible tree: ansible/roles/rabbitmq/tasks/deploy.yml, lines 4-6), so keeping classic queues also needs a manual migration, to mirrored queues, as the HA precheck message says (`roles/rabbitmq/tasks/precheck.yml:115-123`). [NOT AVAILABLE] What oslo.messaging does with existing classic queues when the services restart with `rabbit_quorum_queue = true` |

## Related

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and bugs
  found in `2024.1-eom`
- [Open questions](../troubleshooting/open-questions.md) — among them
  [Q4](../troubleshooting/open-questions.md#q4), which F12 refers to
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Risk register](../risk/risk-register.md) — the risks, from [R1](../risk/risk-register.md#r1)
- [Kolla images](../concepts/kolla-images.md) — the image side of F14 and F15
- [Repository architecture](../concepts/repository-architecture.md) — `kolla_container`, the systemd unit and the
  `common` play (F2, F3, F16)
- [Ansible listings](listings/index.md) — the ansible-core 2.16.20 listings behind F7
- [Per-role fact sheets](factsheets/index.md) — errata with their evidence
