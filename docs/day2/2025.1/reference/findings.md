---
title: Technical findings
description: Findings F1 to F17 of the source study re-checked against 2025.1-eom, plus five new 2025.1 findings, each with its status, evidence and why it matters.
tags: [evidence, handlers, tags, limit, serial, images, kolla-set-configs, one-shot, reconfigure, nova, neutron, haproxy, docker, podman, systemd, rabbitmq]
remember:
  - "Changed in 2025.1: the restart blast radius is per container. A nova-compute-only change restarts <code>nova_compute</code> alone; loop-notify amplification no longer holds. <span class=\"ev ev-code\">CODE</span>"
  - "Same-tag image rebuilds are still not picked up by <code>deploy</code>/<code>reconfigure</code>/<code>upgrade</code>, with Docker or Podman: only absent images are pulled; an explicit <code>pull</code> is required. <span class=\"ev ev-code\">CODE</span>"
  - "A <code>reconfigure</code> is a <code>deploy</code> (53 of the 54 roles that have one): it applies schema migrations if the image tag moved, Neutron included. <span class=\"ev ev-code\">CODE</span>"
  - "New in 2025.1: <code>-t &lt;service&gt;</code> rewrites that service's HAProxy frontend but no longer restarts HAProxy, so the new frontend waits for a run of the loadbalancer play. <span class=\"ev ev-code\">CODE</span>"
  - "New in 2025.1: <code>reconfigure</code> and <code>upgrade</code> always run with <code>kolla_serial=0</code>, whatever you pass with <code>-e</code>; batch with <code>deploy -e kolla_serial=N</code>. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "In 2025.1, a config change touches one nova-compute container only. Which containers of that host restart?"
    options: ["Every container of that role on that host, as in 2024.1", "Only <code>nova_compute</code>, the container whose check reports a change"]
    answer: 1
    explain: "F1 no longer holds in 2025.1 <span class=\"ev ev-code\">CODE</span>: the config tasks do not notify, and <code>service-check-containers</code> notifies only the items its <code>compare_container</code> loop found changed."
    see: "f1--loop-notify-amplification"
  - q: "In 2025.1, you add a backend option to Keystone's HAProxy frontend and run <code>kolla-ansible deploy -t keystone</code>. When does HAProxy use the new frontend?"
    options: ["At the end of the run: the frontend task restarts HAProxy", "Not until a run that includes the loadbalancer play's final check, for example <code>-t haproxy</code> or a run without tags"]
    answer: 1
    explain: "F18 <span class=\"ev ev-code\">CODE</span>: the frontend task no longer notifies, and the final <code>check-containers</code> include of the loadbalancer play carries only the play tags (<code>haproxy</code>, <code>keepalived</code>, <code>loadbalancer</code>), so <code>-t keystone</code> skips it. Ansible's own listing shows it. Left for the community to confirm."
    see: "f18---t-service-no-longer-restarts-haproxy"
  - q: "What does <code>kolla-ansible reconfigure -e kolla_serial=1</code> do in 2025.1?"
    options: ["Reconfigures one host at a time", "Runs with <code>kolla_serial=0</code>: the command adds its own value after yours"]
    answer: 1
    explain: "F19 <span class=\"ev ev-code\">CODE</span>: <code>Reconfigure</code> and <code>Upgrade</code> set <code>kolla_serial</code> to 0 in their own extra vars, which come after the user's <code>-e</code>, and the later value wins. Use <code>deploy -e kolla_serial=1</code>, which runs the same tasks."
    see: "f19--reconfigure-and-upgrade-cannot-be-batched"
  - q: "You upgraded a Docker-based cloud on Ubuntu from 2024.1 to 2025.1. A container was left out of the upgrade. What happens at its next 2025.1 <code>deploy</code>, with no other change?"
    options: ["Nothing: its config and image are unchanged", "Its check reports a change: the unit file lacks <code>PartOf=kolla.target</code>, and its <code>ulimits</code> differ from the new defaults, so it is restarted or recreated"]
    answer: 1
    explain: "F16 <span class=\"ev ev-code\">CODE</span>: <code>compare_container</code> compares the whole unit file text and the container dimensions, ulimits included, and both changed between 2024.1 and 2025.1."
    see: "f16--the-first-20251-check-restarts-a-container-whose-unit-20241-wrote"
---

# Technical findings

The study consolidates three things. This page holds the first:

1. what was established and how (evidence level): the headline findings below;
2. implementation limitations and bugs found in `2025.1-eom`: [Known bugs and
   limitations](../troubleshooting/known-bugs-and-limitations.md);
3. what the sources do not establish: [Open questions](../troubleshooting/open-questions.md) and [What is not
   known](../troubleshooting/what-is-not-known.md).

> [!NOTE]
> **Key answers**
>
> - **Seventeen headline findings ([F1–F17](#f1))**, first established on `ussuri-eol` (F16 and F17 on `2024.1-eom`),
>   re-checked against `2025.1-eom`, each with its 2025.1 evidence and why it matters, plus **five new 2025.1
>   findings** ([F18](#f18) to [F22](#f22)) ([Headline findings](#headline-findings)).
> - **Still hold in 2025.1:** same-tag image rebuilds ([F4](#f4)), `reconfigure` = `deploy` ([F5](#f5), now 53 of 54
>   roles), global inputs in per-host files ([F6](#f6)), [F7](#f7) and [F10](#f10) (re-read in ansible-core 2.18.20),
>   `--limit` not confining actions ([F8](#f8), with more delegated steps), sequential delegated facts ([F9](#f9), now
>   with a variable to narrow them), [F12](#f12), [F15](#f15), the unit-file restart after an upgrade ([F16](#f16),
>   with a new unit text) and quorum queues ([F17](#f17), now the only choice).
> - **No longer hold in 2025.1:** loop-notify amplification ([F1](#f1)); the part of [F13](#f13) that put nova-compute
>   before OVS. **Still no longer hold:** [F2](#f2), [F3](#f3), [F11](#f11). **Narrower:** the
>   `kolla_set_configs --check` blind spots ([F14](#f14): a changed command or a dropped entry is now detected).
> - **New in 2025.1:** `-t <service>` no longer restarts HAProxy ([F18](#f18)); `reconfigure` and `upgrade` cannot be
>   batched with `kolla_serial` ([F19](#f19)); every compute asks the Nova API for all hypervisors, through the first
>   conductor, also in `genconfig` ([F20](#f20)); a dropped `config.json` entry makes the check restart the container on
>   every run until it is recreated ([F21](#f21)); `ovs_wrapper` does not reach the Open vSwitch daemons on stop
>   ([F22](#f22)). All five are read from the code and are left for the community to confirm.

Evidence levels: **[CODE]** and **[NOT AVAILABLE]**, defined once, in [Evidence
labels](../start/conventions.md#evidence-labels). The study rests only on reading source code; no run against a host is
used as evidence. Paths are relative to the kolla-ansible `2025.1-eom` checkout (commit `7222f0f`); paths prefixed
`kolla` point into the kolla image repository (`2025.1-eom`, commit `c4b53a2`), and `ansible-core 2.18.20` into the
Ansible source.

## Headline findings

| # | Finding |
|---|---|
| [F1](#f1) | Loop-notify amplification (no longer holds in 2025.1) |
| [F2](#f2) | `-t common` is a no-op (no longer holds) |
| [F3](#f3) | `docker_graceful_timeout` and `docker_client_timeout` are ignored (no longer holds) |
| [F4](#f4) | Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade` |
| [F5](#f5) | `reconfigure` = `deploy` |
| [F6](#f6) | Global inputs are rendered into per-host files |
| [F7](#f7) | `--list-tasks` cannot show what a tag runs |
| [F8](#f8) | `--limit` does not confine actions |
| [F9](#f9) | With `--limit`, all hosts' facts are gathered sequentially |
| [F10](#f10) | `kolla_serial` makes `run_once` steps repeat per batch |
| [F11](#f11) | The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides (no longer holds) |
| [F12](#f12) | The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes` |
| [F13](#f13) | The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes (before the Neutron agents only, in 2025.1) |
| [F14](#f14) | `kolla_set_configs --check` has blind spots (fewer in 2025.1) |
| [F15](#f15) | What the bootstrap containers run differs per image |
| [F16](#f16) | The first 2025.1 check restarts a container whose unit 2024.1 wrote |
| [F17](#f17) | RabbitMQ quorum queues are on by default (the only choice in 2025.1) |
| [F18](#f18) | `-t <service>` no longer restarts HAProxy (new in 2025.1) |
| [F19](#f19) | `reconfigure` and `upgrade` cannot be batched (new in 2025.1) |
| [F20](#f20) | Every compute lists all hypervisors through the first conductor (new in 2025.1) |
| [F21](#f21) | A dropped `config.json` entry restarts the container on every run until it is recreated (new in 2025.1) |
| [F22](#f22) | `ovs_wrapper` does not stop the Open vSwitch daemons cleanly (new in 2025.1) |

<a id="f1"></a>

### F1 — Loop-notify amplification

**No longer holds in 2025.1** [CODE]. The ansible-core mechanism is still there; Kolla's tasks no longer use it.

| | |
|---|---|
| **Finding** | **Ussuri to 2024.1:** when a looped config/check task notified `Restart {{ item.key }} container` and *one* item changed, the handlers of *all* executed items were notified, so a nova-compute-only change restarted `nova_libvirt` and `nova_ssh` too. **2025.1:** the config tasks no longer notify (one exception: Placement's WSGI file, and the Cinder Huawei XML files, [Conventions](../start/conventions.md)). Every role's `check-containers.yml` imports the shared `service-check-containers` role, which runs `compare_container` in a loop without `notify`, then notifies from a separate, non-looped task the handlers of only the items whose result is changed. A nova-compute-only change restarts `nova_compute` alone; a scheduler-only change restarts `nova_scheduler`; a change of one agent's file on a network node restarts that agent |
| **Evidence** | [CODE] `roles/service-check-containers/tasks/main.yml:4-29` (the loop, with `register: container_check` and no `notify`), `:34-41` (`notify` built from `container_check.results \| select('changed')`); `roles/nova-cell/tasks/check-containers.yml:2-3`, `roles/neutron/tasks/check-containers.yml:2-3` (import of the shared role); `roles/nova-cell/tasks/config.yml:112-118` (config task without `notify`); `releasenotes/notes/refactor-container-check-27624449c47f5e6e.yaml:3-21`. The ansible-core side is unchanged: a looped task with `notify` still notifies the handlers of every executed item when the task result is changed (ansible-core 2.18.20 `lib/ansible/plugins/strategy/__init__.py:640-653`); walk-through in [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code) |
| **Why it matters** | Restart blast radius is now per container. libvirt restarts only when its own image, options or files change. A global input still restarts every container whose files it reaches ([F6](#f6)) |

<a id="f2"></a>

### F2 — `-t common` is a no-op

**No longer holds in 2025.1** [CODE], as in 2023.1 and 2024.1. `common` is a play of its own, with play-level
`tags: common` (`site.yml:88-103`), and no role has a `meta/` directory, so nothing else reaches the role. The included
tasks inherit the play tag, so `-t common` renders the common configs and restarts what changed.

| | |
|---|---|
| **Finding** | **Ussuri:** `-t common` was a no-op, because tags on the dynamic `include_tasks` do not propagate to the included tasks. **2025.1:** `roles/common/tasks/main.yml:2` is a bare `include_tasks: "{{ kolla_action }}.yml"`, reached only from the `Apply role common` play; `-t common` runs it on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` hosts, and a service tag (e.g. `-t nova`) skips it. **Changed in 2025.1:** the fluentd `ensure_image` of 2024.1 is gone, so `-t common` and `genconfig` no longer pull that image; the common `config.yml` now installs `/etc/systemd/system/kolla.target`, which every container unit is part of ([F16](#f16)) |
| **Evidence** | [CODE] `site.yml:88-103`; `roles/common/tasks/main.yml:2`; `roles/common/tasks/config.yml:54-58`; ansible-core 2.18.20 `lib/ansible/playbook/taggable.py:40` (`tags` is an extending attribute), `lib/ansible/playbook/block.py:309-359` (a block's value extends its parent's, role's and play's, `:350-359` for the play), `lib/ansible/plugins/strategy/linear.py:274` (included blocks are filtered by tag) ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code); [R25](../risk/risk-register.md#r25); [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard)) |
| **Why it matters** | `common` changes (fluentd/cron/toolbox) are applied by `-t common` or by an untagged run, and never by a service-tagged run: a fluentd/logrotate change made when enabling a service with `deploy -t <svc>` waits for the next run of the common play ([R2](../risk/risk-register.md#r2)) |

<a id="f3"></a>

### F3 — `docker_graceful_timeout` and `docker_client_timeout` are ignored

**No longer holds in 2025.1** [CODE], as in 2023.1 and 2024.1. `kolla_container` still declares the two options
without an argument default, so the values from `docker_common_options` are used; containers (except one-shots) run
under a systemd unit whose `ExecStop` carries the graceful timeout, for Docker and Podman
([R24](../risk/risk-register.md#r24)).

| | |
|---|---|
| **Finding** | **Ussuri:** the `kolla_docker` argument defaults (10 s, 120 s) overrode `common_options`, so every stop sent SIGKILL 10 s after SIGTERM. **2025.1:** `graceful_timeout` and `client_timeout` are declared without a default, so the `common_options` values (`docker_graceful_timeout: 60`, `docker_client_timeout: 120`) are taken; the 10 s and 120 s values apply only when neither is given. A restart or stop of a long-running container goes through the unit `kolla-<name>-container.service`, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`. Without a unit file the Docker worker calls the engine's `stop` with the same timeout |
| **Evidence** | [CODE] `library/kolla_container.py:311, :333` (no default), `:357-389` (common-options merge, fallback 10/120 at `:366-367`); `group_vars/all.yml:114, :148, :151-162`; `module_utils/kolla_systemd_worker.py:20-40` (template, `ExecStop` at `:33`), `:51-55` (engine dependency); `module_utils/kolla_docker_worker.py:426-442` (stop), `:450-470` (restart); `module_utils/kolla_podman_worker.py:125-127` (the timeout passed to Podman as `stop_timeout`), `:677-695, :704-719` |
| **Why it matters** | A service still running 60 s after SIGTERM is killed with its in-flight work (heat-engine, cinder copies, glance uploads); raising `docker_graceful_timeout` has an effect (it reaches the unit on the next restart, [R24](../risk/risk-register.md#r24), and changing it changes the unit text, which `compare_container` detects, [F16](#f16)). [NOT AVAILABLE] systemd's own stop timeout for these units (the unit sets none) |

<a id="f4"></a>

### F4 — Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`

**Still holds in 2025.1** [CODE], for the Docker worker and for the Podman worker.

| | |
|---|---|
| **Finding** | **Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`.** Only absent images are pulled; an explicit `pull` is required. **New in 2025.1, one exception for `nova_libvirt`:** the libvirt version check reads the local image of the tag on the first compute and runs `libvirtd --version` in the running container of every compute whose image id differs; it reads, it does not pull ([F8](#f8)) |
| **Evidence** | [CODE] Docker: `module_utils/kolla_docker_worker.py:107-122` (the container's image id is compared with the local image of that tag), `:376-378` (`start_container`: `check_image`, then `pull_image` only when the image is absent), `:524-526` (`ensure_image`, same rule). Podman: `module_utils/kolla_podman_worker.py:360-378` (same comparison), `:789-791` (`ensure_image` pulls only an absent image). Version check: `roles/nova-cell/tasks/version-check.yml:30-33, :45-56` ([R13](../risk/risk-register.md#r13)) |
| **Why it matters** | Mutable tags create silent drift between hosts. A later unrelated `pull` turns into a mass recreate |

<a id="f5"></a>

### F5 — `reconfigure` = `deploy`

**Still holds in 2025.1** [CODE], in 53 of 54 roles (swift is gone; bifrost keeps its own logic).

| | |
|---|---|
| **Finding** | **`reconfigure` = `deploy`** for 53 of the 54 roles that have a `tasks/reconfigure.yml` (only bifrost has its own logic). A reconfigure re-runs Keystone registration, DB creation/grants and the DB-sync bootstrap containers of the services. `bootstrap_neutron` is imported without any condition and runs on every `deploy` and `reconfigure`; `neutron_enable_rolling_upgrade` is read only by `upgrade.yml`. No task tests `kolla_action == "reconfigure"` alone, so `deploy` and `reconfigure` run the same tasks, which is what makes `deploy -e kolla_serial=N` the batchable form of a reconfigure ([F19](#f19)) |
| **Evidence** | [CODE] `roles/*/tasks/reconfigure.yml` (e.g. `roles/nova-cell/tasks/reconfigure.yml:2`); `roles/neutron/tasks/deploy.yml:20`, `roles/neutron/tasks/bootstrap.yml:38`, `roles/neutron/tasks/bootstrap_service.yml:2-21`, `roles/neutron/tasks/upgrade.yml:4-8`, `roles/neutron/defaults/main.yml:707` ([Repository architecture §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). One-shot containers counted from the code: `-t nova` starts 6 on `control01` when cell0 is mapped and the cell is unchanged (API DB sync, `map_cell0`, `list_cells` ×3, cell DB sync: `nova.yml:49-55`, `roles/nova/tasks/bootstrap.yml:54-56`, `roles/nova/tasks/map_cell0.yml:2-30, :63-67`, `roles/nova-cell/tasks/bootstrap.yml:41-43`, `create_cells.yml:2-4`, `discover_computes.yml:4-5, :21`, `get_cell_settings.yml:2-21`), and **new in 2025.1**, 2 more on the first compute, `libvirt_version_check` and `nova_libvirt_script_check` (`roles/nova-cell/tasks/version-check.yml:3-21, :80-98`); on `reconfigure -t neutron` the neutron role starts one, `bootstrap_neutron`, on the first `neutron-server` host (`roles/neutron/tasks/bootstrap_service.yml:20-21`). [NOT AVAILABLE] Totals for a run without a tag, which depend on the enabled services |
| **Why it matters** | A "reconfigure" applies schema migrations if the image tag moved, for Neutron too (`neutron-db-manage … upgrade head` for neutron and each enabled subproject, kolla `docker/neutron/neutron-server/extend_start.sh:5-13`). There is never a "config only" path except `genconfig` + `deploy-containers` (`kolla_ansible/cli/commands.py:113-125`, `:245-256`) |

<a id="f6"></a>

### F6 — Global inputs are rendered into per-host files

**Still holds in 2025.1** [CODE].

| | |
|---|---|
| **Finding** | **Global inputs are rendered into per-host files.** `enable_*` flags, RabbitMQ/memcached membership, service passwords, the oslo.messaging options and the external FQDN end up in compute-side files |
| **Evidence** | [CODE] `group_vars/all.yml:274, :284` (`rpc_transport_url`, `notify_transport_url`: every RabbitMQ host, user and password); `roles/nova-cell/templates/nova.conf.j2:37, :57, :183, :201-206` (transport URLs, console base URL from the public FQDN, quorum and stream options, [F17](#f17)); `roles/neutron/templates/neutron.conf.j2:121` (memcached list), rendered for the OVS agent on computes too (`roles/neutron/tasks/config.yml:73-103`); `roles/common/tasks/config.yml:104-239` (`fluentd.conf` and `logrotate.conf` from the global `enable_*` flags) |
| **Why it matters** | Small central changes cause fleet-wide restarts, now limited to the containers whose files changed ([F1](#f1)) |

<a id="f7"></a>

### F7 — `--list-tasks` cannot show what a tag runs

**Still holds in 2025.1** [CODE], re-read in ansible-core 2.18.20 and seen in its own listing.

| | |
|---|---|
| **Finding** | **`--list-tasks` cannot show what a tag runs**, and `--list-hosts` shows 0 hosts for `&enable_*` plays. **Changed in 2025.1:** the listings cannot be produced through the `kolla-ansible` CLI; they come from `ansible-playbook` directly ([Ansible listings](listings/index.md)) |
| **Evidence** | [CODE] ansible-core 2.18.20 `lib/ansible/cli/playbook.py:179` (host patterns are resolved before any task runs), `:213-218` (the listing walks the statically compiled play, where a dynamic include is one task), `lib/ansible/inventory/manager.py:446-448` (an `&` pattern intersects with a group that does not exist yet); `site.yml:15-74` (the `enable_*` groups are created by `group_by` at run time); [list-tasks-nova.txt](listings/list-tasks-nova.txt) (ansible-core 2.18.20 output on the 2025.1 tree: one `include_tasks` line per nova play, and `Could not match supplied host pattern` warnings for the groups created at run time) |
| **Why it matters** | Operators need `genconfig` or staging to predict a run ([Predict and inspect a run](../operations/predict-a-run.md)) |

<a id="f8"></a>

### F8 — `--limit` does not confine actions

**Still holds in 2025.1** [CODE], with more delegated steps.

| | |
|---|---|
| **Finding** | **`--limit` does not confine actions.** `delegate_to: groups[x][0]` runs work on hosts outside the limit. With `deploy --limit` set to a compute host, `control01` (the first `neutron-server` and `nova-conductor` host of the `multinode` inventory) runs the Neutron DB create/grant and the `bootstrap_neutron` container, plus cell discovery (`nova_list_cells`, `openstack compute service list`, `nova-manage cell_v2 discover_hosts`). **New in 2025.1:** `control01` also runs the hypervisor list for every limited compute ([F20](#f20)), and the libvirt version check runs its one-shot containers and its image read on the **first compute of the inventory**, even when that compute is outside the limit (`delegate_to: groups[service.group] \| first`). The nova-cell RabbitMQ user/vhost creation is delegated too (to the first RabbitMQ host), but it runs only when the first nova-conductor is inside the limit |
| **Evidence** | [CODE] `site.yml:669-691` and `nova.yml:125-147` (both plays include `compute`); `roles/neutron/tasks/bootstrap.yml:13-14, :33-34`, `roles/neutron/tasks/bootstrap_service.yml:20-21`; `roles/nova-cell/tasks/deploy.yml:21-39`, `wait_discover_computes.yml:8-43, :87-90`, `discover_computes.yml:4-23`, `get_cell_settings.yml:2-21`; `roles/nova-cell/tasks/config.yml:59-73`; `roles/nova-cell/tasks/version-check.yml:20-21, :97-98`, `roles/service-image-info/defaults/main.yml:3`; `roles/nova-cell/tasks/rabbitmq.yml:10-12`; `inventory/multinode:3-6, :99-100, :229-230, :254-255` ([Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node)) |
| **Why it matters** | "Only the new compute" still executes DB-sync containers on a controller, and now also starts containers on another compute |

<a id="f9"></a>

### F9 — With `--limit`, all hosts' facts are gathered sequentially

**Still holds in 2025.1 by default** [CODE], re-read in ansible-core 2.18.20; the list can now be narrowed.

| | |
|---|---|
| **Finding** | **With `--limit`, all hosts' facts are gathered sequentially** by the limited hosts (delegated loop). **New in 2025.1:** the hosts gathered are those of `kolla_ansible_delegate_facts_hosts`, `groups['all']` by default, which an operator can set to a shorter list |
| **Evidence** | [CODE] `gather-facts.yml:34-62` (each limited host loops over its share of the list, `:47`; skipped for hosts in the limit and for hosts that already have facts, `:59-61`); `group_vars/all.yml:43`; `doc/source/user/ansible-tuning.rst:164-203`; loop items run one after another in the same worker (ansible-core 2.18.20 `lib/ansible/executor/task_executor.py:299`, each item through `_execute` at `:347`) ([R23](../risk/risk-register.md#r23); [Compute scaling §6](../concepts/compute-scaling-and-performance.md#6-scaling-at-3-10-and-30-computes-read-from-the-code)) |
| **Why it matters** | O(total hosts) serial latency on every limited run without fact caching, unless the list is narrowed |

<a id="f10"></a>

### F10 — `kolla_serial` makes `run_once` steps repeat per batch

**Still holds in 2025.1** [CODE], re-read in ansible-core 2.18.20, for the commands that accept `kolla_serial`
([F19](#f19)).

| | |
|---|---|
| **Finding** | **`kolla_serial` makes `run_once` steps repeat per batch** (API DB sync ×3 with serial 1 and the three controllers of the `multinode` inventory; in 2025.1 also the libvirt version check's one-shot containers, once per batch of the nova-cell play) and orders a play's restarts by host-pattern order (computes before conductors in the nova-cell play) |
| **Evidence** | [CODE] ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:183-191` (one strategy run per batch, with the inventory restricted to the batch), `:276` (batches follow the play's host order), `lib/ansible/plugins/strategy/linear.py:178, :205-206` (a `run_once` task is queued for the first host left, then the host loop stops), `lib/ansible/inventory/manager.py:408-410` (restriction to the batch); `roles/nova/tasks/bootstrap_service.yml:2-21`; `roles/nova-cell/tasks/version-check.yml:20, :97`; `nova.yml:29-55, :125-147`; `inventory/multinode:3-6, :99-100, :226-227` ([Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)) |
| **Why it matters** | Batching reduces blast radius but multiplies bootstrap work, and exposes ordering within a play |

<a id="f11"></a>

### F11 — The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides

**No longer holds in 2025.1** [CODE], as in 2023.1 and 2024.1. `ml2_conf.ini` is rendered only for `neutron-server` and
`neutron-infoblox-ipam-agent`; `openvswitch_agent.ini` has its own template and override files
([R5](../risk/risk-register.md#r5)).

| | |
|---|---|
| **Finding** | **Ussuri:** the `openvswitch_agent.ini` merge included the operator's `ml2_conf.ini` overrides. **2025.1:** `openvswitch_agent.ini` merges `templates/openvswitch_agent.ini.j2` with `neutron/openvswitch_agent.ini` and `neutron/<host>/openvswitch_agent.ini` only |
| **Evidence** | [CODE] `roles/neutron/tasks/config.yml:134-150` (`services_need_ml2_conf_ini`), `:152-164` (`openvswitch_agent.ini`); `roles/neutron/tasks/deploy.yml:11-23` (config, then `check-containers.yml`, then `Flush Handlers`); `roles/neutron/tasks/check-containers.yml:2-3` |
| **Why it matters** | Server-side ML2 changes do not restart any OVS agent; **changed in 2025.1**, they restart `neutron_server` alone, not the other neutron containers of its host ([F1](#f1), [R5](../risk/risk-register.md#r5)). OVS agent options belong in `neutron/openvswitch_agent.ini` |

<a id="f12"></a>

### F12 — The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes`

**Still holds in 2025.1** [CODE], unless the new agent wrappers are on.

| | |
|---|---|
| **Finding** | **The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start** when `enable_neutron_agent_ha: yes` (default `no`); its comment says this removes all L3 namespaces (what the command does is neutron code: [NOT AVAILABLE]). **New in 2025.1:** the cleanup is skipped when `neutron_agents_wrappers` is on (default `no`) |
| **Evidence** | [CODE] `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-16`; `group_vars/all.yml:934`; `roles/neutron/defaults/main.yml:646` |
| **Why it matters** | [NOT AVAILABLE] Whether an L3 agent restart interrupts router traffic on that node ([Q4](../troubleshooting/open-questions.md#q4)). `neutron_l3_agent_failover_delay` (default `0`, `roles/neutron/defaults/main.yml:626`) spaces the restarts of running L3 agents across hosts when set above `0`; with the default they are not spaced (`roles/neutron/handlers/main.yml:67-134`) ([R6](../risk/risk-register.md#r6)) |

<a id="f13"></a>

### F13 — The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes

**Partly no longer holds in 2025.1** [CODE]: Open vSwitch now comes before nova-compute; the Neutron agents still come
after it.

| | |
|---|---|
| **Finding** | **2024.1:** the nova-cell play ran before the `openvswitch` and `neutron` plays. **2025.1:** the `openvswitch`, `ovs-dpdk`, `ovn-controller` and `ovn-db` plays run before the `nova.yml` import, and the `neutron` play right after it. On a new compute, `nova_compute` therefore starts after Open vSwitch and before `neutron_openvswitch_agent` |
| **Evidence** | [CODE] `site.yml:605-619` (`Apply role openvswitch`), `:605-665` (the four network plays), `site.yml:667` (`import_playbook: nova.yml`, whose `Apply role nova-cell` play is `nova.yml:125-147`), `site.yml:669-691` (`Apply role neutron`) |
| **Why it matters** | [NOT AVAILABLE] Whether instances can be scheduled on such a compute before the neutron play finishes ([Execution flow §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)); relevant when adding computes one by one |

<a id="f14"></a>

### F14 — `kolla_set_configs --check` has blind spots

**Narrower in 2025.1** [CODE]: kolla's `docker/base/set_configs.py` now compares the command and the list of files.

| | |
|---|---|
| **Finding** | **`kolla_set_configs --check` has blind spots, fewer than in 2024.1.** It compares the `config_files` entries of `config.json` (content, mode, owner). **New in 2025.1:** it also reports a difference when the running command, saved in `/run_command` at start, differs from the `command` of `config.json` (so memcached's settings, all in its command, are now detected), and when a file recorded in the defaults state is no longer in `config.json`. **Still blind:** a change confined to the `permissions` section of `config.json`. A newly added optional file reports drift (exit 1), like any missing destination. `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run. With `kolla_container_engine: podman`, a container that is not `running` counts as drift before any check, and an exit code other than 0 or 1 (137 included) fails the task, where the Docker worker treats 137 as drift |
| **Evidence** | [CODE] kolla `docker/base/set_configs.py:178-211` (`_cmp_file`), `:192-198, :219-224` (prometheus extras), `:233-255` (`check`), `:324-330` (`/run_command` written), `:347` (`handle_permissions`, not on the check path, `:655-657`), `:580-586` (`ConfigFileCommandDiffers`), `:589-636` (`StateMismatch`); `module_utils/kolla_docker_worker.py:146-181`; `module_utils/kolla_podman_worker.py:524-552`; `roles/memcached/templates/memcached.json.j2:1-4` ([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)) |
| **Why it matters** | "`genconfig` + `--check`" ([Predict and inspect a run](../operations/predict-a-run.md)) is more reliable than in 2024.1, but a permissions-only change is still not reported. Since restarts now come only from the check ([F1](#f1)), a `config.json` change that the check misses is not applied by any run until the container restarts for another reason. The new dropped-entry test has the opposite problem: it never stops firing ([F21](#f21)) |

<a id="f15"></a>

### F15 — What the bootstrap containers run differs per image

**Still holds in 2025.1** [CODE]: the five kolla start scripts are unchanged from 2024.1.

| | |
|---|---|
| **Finding** | **What the bootstrap containers run differs per image.** Nova's bootstrap containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`). Placement's `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure. Heat's does not re-apply a changed `heat_domain_admin_password` to Keystone (it creates the domain user only when `heat_user_domain` is missing). neutron-server's migrates neutron and each enabled subproject; the bootstrap and the rolling `upgrade` use the same list, the enabled `neutron_subprojects` |
| **Evidence** | [CODE] kolla `docker/nova/nova-api/extend_start.sh:9-30`, `docker/nova/nova-conductor/extend_start.sh:3-17`, `docker/placement/placement-api/extend_start.sh:5-9`, `docker/heat/heat-api/extend_start.sh:5-17`, `docker/neutron/neutron-server/extend_start.sh:5-13, :17-34`; `roles/nova/tasks/bootstrap_service.yml:11`, `roles/nova-cell/tasks/bootstrap_service.yml:11`, `roles/placement/tasks/bootstrap_service.yml:11`, `roles/heat/tasks/bootstrap_service.yml:11, :22`, `roles/neutron/defaults/main.yml:651-663, :702, :708` |
| **Why it matters** | What a "reconfigure" or a tag-changing "deploy" does to databases depends on the image, not only on kolla-ansible ([Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)) |

<a id="f16"></a>
<a id="f16--the-first-20241-check-restarts-a-container-whose-unit-20231-wrote"></a>

### F16 — The first 2025.1 check restarts a container whose unit 2024.1 wrote

**Holds again in 2025.1** [CODE], with a new unit text, and with Docker outside the Red Hat family also through the
new default `ulimits`.

| | |
|---|---|
| **Finding** | **The systemd unit template changed again, and the unit text is part of the container check.** The 2025.1 template adds `PartOf=kolla.target`. `compare_container` reports a change when `check_unit_change` finds that the unit file on disk differs from the rendered template, whole text compared. So the first 2025.1 check of a container whose unit was written by 2024.1 code reports it as changed, even when nothing else differs, and `service-check-containers` notifies its restart handler, which rewrites the unit, reloads systemd and enables it. **Also new in 2025.1:** the default container dimensions set a `nofile` ulimit on every host with Docker (2024.1 set it only on Red Hat family hosts), and `compare_container` compares ulimits, so with Docker on Debian or Ubuntu such a container differs in its options and is **recreated**. A container that a 2025.1 run creates, recreates or restarts gets the new unit and is not flagged again. One-shot containers have no unit |
| **Evidence** | [CODE] `module_utils/kolla_systemd_worker.py:20-40` (template, `PartOf` at `:27`), `:155-168` (`check_unit_change`: whole text), `:173-186` (`create_unit_file`: write, reload, enable); `module_utils/kolla_container_worker.py:58-65` (`compare_container`), `:274-303, :326-336` (ulimits compared); `module_utils/kolla_podman_worker.py:301-308` (same for Podman), `:219-228, :484-500` (Podman filters the two limits out); `group_vars/all.yml:201-224` (default dimensions); `module_utils/kolla_docker_worker.py:352` (`recreate_or_restart_container`), `:450-470` (`restart_container`); `roles/common/tasks/config.yml:54-58` (`kolla.target`) ([Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)) |
| **Why it matters** | After an upgrade from 2024.1, a `deploy`/`reconfigure` that the operator expects to be a no-op restarts every checked container whose unit no 2025.1 run has rewritten yet (for example a role left out of a tagged or `--limit` upgrade), and recreates it with Docker on Debian or Ubuntu. Run that first apply as its own controlled step ([Controlled batches §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern)). Which containers restart on a real platform is left for the community to confirm |

<a id="f17"></a>

### F17 — RabbitMQ quorum queues are on by default

**Holds in 2025.1, and is now the only choice** [CODE].

| | |
|---|---|
| **Finding** | **2024.1:** `om_enable_rabbitmq_quorum_queues` defaulted to `true`, and classic mirrored queues could be kept with `om_enable_rabbitmq_high_availability`. **2025.1:** both variables are gone. Every service renders `rabbit_quorum_queue = true` and `rabbit_transient_quorum_queue = true` unconditionally, and `rabbit_stream_fanout = true` while `om_enable_rabbitmq_stream_fanout` stays `true` (its default). When a `rabbitmq` container exists, `prechecks` lists the queues and fails on any non-quorum queue (except `reply_` and `_fanout` ones), on non-quorum `reply_` queues, and on `_fanout` queues that are not streams while stream fanout is on |
| **Evidence** | [CODE] `group_vars/all.yml:287, :292`; `roles/nova-cell/templates/nova.conf.j2:201-206`, `roles/nova/templates/nova.conf.j2:151-156`, `roles/neutron/templates/neutron.conf.j2:139-144`; `roles/rabbitmq/tasks/precheck.yml:110-163` (`:118-129` quorum, `:131-143` transient, `:145-159` streams, `:162-163` only when the container exists); `site.yml:77-86` (the prechecks play runs only for `kolla_action` `precheck`) |
| **Why it matters** | A cloud that still has classic queues cannot keep them: the precheck message calls the migration manual and says it may take several hours on larger systems (`roles/rabbitmq/tasks/precheck.yml:121-125`). [NOT AVAILABLE] What oslo.messaging does with existing classic queues when the services restart with these options |

<a id="f18"></a>

### F18 — `-t <service>` no longer restarts HAProxy

**New in 2025.1** [CODE], confirmed by ansible-core's own listing; to be confirmed by the community.

| | |
|---|---|
| **Finding** | **A service tag rewrites the service's HAProxy frontend without applying it.** The `haproxy-config` task that writes `services.d/<service>.cfg` no longer notifies `Restart haproxy container` (2024.1 notified it twice). The restart is decided by one `check-containers` include of the `loadbalancer` role at the end of the loadbalancer play, after its 38 service includes. That include has no tags of its own, so it carries only the play tags `haproxy`, `keepalived` and `loadbalancer`. Under `-t keystone` (or any service tag) the service include runs, because it is tagged with the service, and the final check is skipped: the file is written, the running HAProxy keeps the old frontend |
| **Evidence** | [CODE] `roles/haproxy-config/tasks/main.yml:2-14` (writes `services.d/<service>.cfg`, no `notify`); `site.yml:115-118` (play tags), `:319-324` (final `check-containers` include, skipped for `kolla_action == 'config'`), `:325-327` (block `when`); `roles/loadbalancer/templates/haproxy/haproxy.json.j2:16-21` (`services.d` copied at start); [list-tasks-nova.txt](listings/list-tasks-nova.txt) lines 106-109 (under `-t nova` the loadbalancer play lists the `nova-api` and `nova-cell` includes only) ([Tags §2.2](../risk/tags.md#22-handlers-ignore-tags-code)) |
| **Why it matters** | A frontend change made with a service tag stays pending until a run that includes the final check: `-t haproxy`, `-t loadbalancer` or a run without tags. That later run applies every pending frontend at once. Check for the community: change a frontend option, run `deploy -t keystone`, check the HAProxy config in use, then run `deploy -t haproxy` |

<a id="f19"></a>

### F19 — `reconfigure` and `upgrade` cannot be batched

**New in 2025.1** [CODE]; to be confirmed by the community.

| | |
|---|---|
| **Finding** | **`kolla-ansible reconfigure` and `kolla-ansible upgrade` always run with `kolla_serial=0`.** The value is a module constant of the new Python CLI (2024.1 read `ANSIBLE_SERIAL` from the environment). The command's own extra vars are added after the user's `-e` options, and ansible-core keeps the later value, so `reconfigure -e kolla_serial=1` runs every play on all its hosts at once. `deploy`, `deploy-containers` and `bootstrap-servers` set no `kolla_serial` and accept the user's value |
| **Evidence** | [CODE] `kolla_ansible/cli/commands.py:20-22` (`ANSIBLE_SERIAL = 0`), `:136` (Reconfigure), `:278` (Upgrade); `kolla_ansible/ansible.py:261-266` (user `-e`, then the command's extra vars); ansible-core 2.18.20 `lib/ansible/utils/vars.py:94-105, :198-224` (`-e` options merged in order, the later value replaces the earlier) ([Controlled batches §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure)) |
| **Why it matters** | A rolling reconfigure is `deploy -e kolla_serial=N`, which runs the same tasks ([F5](#f5)). A rolling upgrade with `kolla_serial` is not possible through the CLI. Check for the community: `upgrade -e kolla_serial=30%` and check the batches in the output |

<a id="f20"></a>

### F20 — Every compute lists all hypervisors through the first conductor

**New in 2025.1** [CODE]; to be confirmed by the community.

| | |
|---|---|
| **Finding** | **The nova-cell `config.yml` writes a `compute_id` file for every compute from a Nova API answer.** For each compute it runs `openstack.cloud.resources` (type `hypervisor`) through `kolla_toolbox`, delegated to the first conductor, without `run_once` and without `failed_when`; then it matches the compute's node name and writes the hypervisor id, or a UUID derived from the node name when no hypervisor matches. A run on C computes makes C such calls on one controller, each listing every hypervisor. It runs in `deploy`, `reconfigure` and `genconfig`, since `genconfig` runs `config.yml` too. `nova-compute.json.j2` copies the file to `/var/lib/nova/compute_id` |
| **Evidence** | [CODE] `roles/nova-cell/tasks/config.yml:53-110` (`:59-73` the list, delegated at `:73`; `:93-101` matched id; `:104-110` generated UUID); `roles/nova-cell/tasks/main.yml:2`; `library/kolla_toolbox.py:135-151, :155` (an `ansible localhost -m …` run inside the container); `roles/nova-cell/templates/nova-compute.json.j2:10-15` ([Compute scaling §3](../concepts/compute-scaling-and-performance.md#3-expensive-tasks-and-their-scaling-factors)) |
| **Why it matters** | A no-change `reconfigure -t nova` now depends on the Nova API being up, and loads the first conductor and the API in proportion to C², read from the code. A failed call fails that compute. The first 2025.1 run restarts `nova_compute` everywhere because its `config.json` gains the entry. Check for the community: time and load of a `-t nova` run with many computes, and `genconfig` with the Nova API down |

<a id="f21"></a>

### F21 — A dropped `config.json` entry restarts the container on every run until it is recreated

**New in 2025.1** [CODE]; the state logic was also run outside a container, not yet on a lab.

| | |
|---|---|
| **Finding** | **`kolla_set_configs --check` raises `StateMismatch` (exit 1) when a destination recorded in the container's defaults state is no longer a destination of `config.json`, and nothing ever removes a recorded destination from that state.** The state file is in the container layer and survives a restart; only a recreate starts a new one. So once an entry is dropped (for example `libvirt_enable_sasl` or `kolla_copy_ca_into_containers` turned off), every `deploy`, `reconfigure` and `deploy-containers` reports the container as changed and restarts it, until a new image or changed parameters recreate it. The same state code (unchanged since 2024.1) also swaps each saved entry in place, so from the third start the "original" kept for a destination that existed in the image is an earlier rendered file |
| **Evidence** | [CODE] kolla `docker/base/set_configs.py:589-642` (`execute_config_check`, `:626-636` `StateMismatch`), `:476-498` (`remove_or_restore_configs`: no key removed, entry swapped at `:496`), `:501-537` (`backup_configs`: keys only added), `:540-556` (`handle_defaults`, state rewritten at `:556`), `:38, :453-458` (state in `/etc/kolla/defaults`); `module_utils/kolla_docker_worker.py:171-172` (exit 1 is a change). A run of these functions outside a container, with one image file and one dropped entry, gave `StateMismatch` after the restart and an earlier rendered file in place of the image's ([Kolla images §2.3](../concepts/kolla-images.md#23-kolla_set_configs-copy-and-permissions), [§6](../concepts/kolla-images.md#6-day-2-consequences) item 4) |
| **Why it matters** | A cloud where an option was turned off sees the same containers restart on every run, which looks like drift that never settles; for `nova_libvirt` that is a restart of the hypervisor's libvirt on every run. Check for the community: turn off `libvirt_enable_sasl` on one compute, run `reconfigure` twice, watch the restarts and the check output, then check whether removing the container and running `deploy-containers` ends the loop |

<a id="f22"></a>

### F22 — `ovs_wrapper` does not stop the Open vSwitch daemons cleanly

**New in 2025.1** [CODE]; the handler pattern was run in bash, not yet on a lab.

| | |
|---|---|
| **Finding** | **Both Open vSwitch containers now run under kolla's `ovs_wrapper`, whose stop handler cannot reach the daemon.** On TERM or QUIT the wrapper runs `ovs-appctl -T1 -t /run/openvswitch/$1.$child.ctl exit`, then exits 0. Inside the handler function `$1` is the function's own first argument, and `trap` passes none, so the path is `/run/openvswitch/.<pid>.ctl`, not the daemon's control socket. The daemon is not asked to exit; the wrapper, which is the container's main process, exits at once |
| **Evidence** | [CODE] kolla `docker/openvswitch/openvswitch-base/ovs_wrapper.sh:3-19`; `roles/openvswitch/templates/openvswitch-vswitchd.json.j2:2`, `roles/openvswitch/templates/openvswitch-db-server.json.j2:2`. A bash run of the same handler pattern printed `/run/openvswitch/.<pid>.ctl` ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)) |
| **Why it matters** | `ovs-vswitchd` and `ovsdb-server` then end when the container's processes are killed, without their own shutdown. [NOT AVAILABLE] Whether that changes anything for flows and `conf.db` compared with a clean exit. Check for the community: stop `openvswitch_vswitchd` and read the end of `ovs-vswitchd.log` |

## Related

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and bugs
  found in `2025.1-eom`
- [Open questions](../troubleshooting/open-questions.md) — among them
  [Q4](../troubleshooting/open-questions.md#q4), which F12 refers to
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Risk register](../risk/risk-register.md) — the risks, from [R1](../risk/risk-register.md#r1)
- [Kolla images](../concepts/kolla-images.md) — the image side of F14 and F15
- [Repository architecture](../concepts/repository-architecture.md) — `kolla_container`, the systemd unit and the
  `common` play (F2, F3, F16)
- [Ansible listings](listings/index.md) — the ansible-core 2.18.20 listings behind F7 and F18
- [Per-role fact sheets](factsheets/index.md) — errata with their evidence
