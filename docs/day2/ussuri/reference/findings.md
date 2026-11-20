---
title: Technical findings
description: The fifteen headline findings of the Kolla-Ansible ussuri-eol source study, F1 to F15, each with its evidence and why it matters.
tags: [evidence, loop-notify, tags, limit, serial, images, kolla-set-configs, one-shot, reconfigure, nova, neutron, docker]
remember:
  - "Restart blast radius is per role-on-host, not per container: a nova-compute-only change restarts <code>nova_libvirt</code> and <code>nova_ssh</code>. <span class=\"ev ev-code\">CODE</span>"
  - "<code>-t common</code> is a no-op: <code>common</code> changes (fluentd/cron/toolbox) are applied by whatever run first reaches the host, often unexpectedly. <span class=\"ev ev-code\">CODE</span>"
  - "<code>docker_graceful_timeout</code> is ignored: every stop sends SIGKILL to a container still running 10 s after SIGTERM. <span class=\"ev ev-code\">CODE</span>"
  - "Same-tag image rebuilds are not picked up by <code>deploy</code>/<code>reconfigure</code>/<code>upgrade</code>: only absent images are pulled; an explicit <code>pull</code> is required. <span class=\"ev ev-code\">CODE</span>"
  - "<code>--limit</code> does not confine actions: \"only the new compute\" still executes DB-sync containers on a controller. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "In Ussuri, how long does a container still running after SIGTERM get before it is killed on a stop?"
    options: ["60 s, the value of <code>docker_graceful_timeout</code>", "10 s: the <code>kolla_docker</code> argument defaults override <code>common_options</code>"]
    answer: 1
    explain: "<code>docker_graceful_timeout</code> and <code>docker_client_timeout</code> are ignored <span class=\"ev ev-code\">CODE</span>: the argument defaults (10 s, 120 s) override <code>common_options</code>, so every stop sends SIGKILL to a container still running 10 s after SIGTERM. The release note claiming 60 s has no effect."
    see: "f3--docker_graceful_timeout-and-docker_client_timeout-are-ignored"
  - q: "In Ussuri, what does <code>-t common</code> do?"
    options: ["Nothing: it is a no-op, because tags on the dynamic <code>include_tasks</code> do not propagate to the included tasks", "It renders the common configs and restarts what changed"]
    answer: 0
    explain: "<code>-t common</code> is a no-op <span class=\"ev ev-code\">CODE</span>. <code>common</code> changes (fluentd/cron/toolbox) are applied by whatever run first reaches the host, often unexpectedly."
    see: "f2---t-common-is-a-no-op"
  - q: "In Ussuri, with default flags, does <code>reconfigure</code> run Neutron's DB sync?"
    options: ["Yes: as for most services, it re-runs the DB-sync bootstrap container", "Only when <code>neutron_enable_rolling_upgrade</code> is left at its default", "No: with the default <code>neutron_enable_rolling_upgrade: \"yes\"</code>, <code>bootstrap_neutron</code> runs on <code>deploy</code> but is skipped on <code>reconfigure</code>"]
    answer: 2
    explain: "Neutron is the exception to <code>reconfigure</code> = <code>deploy</code> <span class=\"ev ev-code\">CODE</span>: a reconfigure re-runs Neutron's DB create/grant tasks but not its DB sync. Only non-default flags (<code>enable_neutron_sfc</code>, or <code>neutron_enable_rolling_upgrade: \"no\"</code>) make it apply Neutron schema migrations."
    see: "f5--reconfigure--deploy"
---

# Technical findings

The study consolidates three things. This page holds the first:

1. what was established and how (evidence level): the headline findings below;
2. implementation limitations and bugs found in `ussuri-eol`: [Known bugs and
   limitations](../troubleshooting/known-bugs-and-limitations.md);
3. what the sources do not establish: [Open questions](../troubleshooting/open-questions.md) and [What is not
   known](../troubleshooting/what-is-not-known.md).

> [!NOTE]
> **Key answers**
>
> - **Fifteen headline findings ([F1–F15](#f1))**, each with its evidence and why it matters, among them loop-notify
>   amplification ([F1](#f1)), the `-t common` no-op ([F2](#f2)), the ignored stop timeout ([F3](#f3)), same-tag image
>   rebuilds ([F4](#f4)) and `reconfigure` = `deploy` ([F5](#f5)) ([Headline findings](#headline-findings)).

Evidence levels: **[CODE]** and **[NOT AVAILABLE]**, defined once, in [Evidence
labels](../start/conventions.md#evidence-labels). The study rests only on reading source code; no run against a host is
used as evidence.

## Headline findings

| # | Finding |
|---|---|
| [F1](#f1) | Loop-notify amplification |
| [F2](#f2) | `-t common` is a no-op |
| [F3](#f3) | `docker_graceful_timeout` and `docker_client_timeout` are ignored |
| [F4](#f4) | Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade` |
| [F5](#f5) | `reconfigure` = `deploy` |
| [F6](#f6) | Global inputs are rendered into per-host files |
| [F7](#f7) | `--list-tasks` cannot show what a tag runs |
| [F8](#f8) | `--limit` does not confine actions |
| [F9](#f9) | With `--limit`, all hosts' facts are gathered sequentially |
| [F10](#f10) | `kolla_serial` makes `run_once` steps repeat per batch |
| [F11](#f11) | The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides |
| [F12](#f12) | The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes` |
| [F13](#f13) | The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes |
| [F14](#f14) | `kolla_set_configs --check` has blind spots |
| [F15](#f15) | What the bootstrap containers run differs per image |

<a id="f1"></a>

### F1 — Loop-notify amplification

| | |
|---|---|
| **Finding** | **Loop-notify amplification.** When a config/check task loops over a role's services and *one* item changes, Ansible 2.9 notifies the handlers of *all* executed items. In Kolla this means a change for one container restarts every container of that role on that host. A nova-compute-only change restarts `nova_libvirt` and `nova_ssh`; a scheduler-only change restarts `nova_api`; a change on a network node restarts all neutron agents there |
| **Evidence** | [CODE] ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:616-623`, `lib/ansible/executor/task_executor.py:790`; `roles/nova-cell/tasks/check-containers.yml:2-20`, `roles/nova/tasks/config.yml:51-69`, `roles/neutron/tasks/check-containers.yml:2-18`; walk-through in [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| **Why it matters** | Restart blast radius is per *role-on-host*, not per container. libvirt restarts far more often than operators expect |

<a id="f2"></a>

### F2 — `-t common` is a no-op

| | |
|---|---|
| **Finding** | **`-t common` is a no-op.** Tags on the dynamic `include_tasks` do not propagate to the included tasks |
| **Evidence** | [CODE] `roles/common/tasks/main.yml:1-10`; ansible 2.9.27 `lib/ansible/playbook/task_include.py:135-154`, `lib/ansible/playbook/block.py:311-314,329-360,378-380`, `lib/ansible/plugins/strategy/linear.py:371` ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)) |
| **Why it matters** | `common` changes (fluentd/cron/toolbox) are applied by whatever run first reaches the host, often unexpectedly |

<a id="f3"></a>

### F3 — `docker_graceful_timeout` and `docker_client_timeout` are ignored

| | |
|---|---|
| **Finding** | **`docker_graceful_timeout` and `docker_client_timeout` are ignored.** The `kolla_docker` argument defaults (10 s, 120 s) override `common_options`, so every stop sends SIGKILL to a container still running **10 s** after SIGTERM |
| **Evidence** | [CODE] `kolla_docker.py:991,1011,1037-1047`; `group_vars/all.yml:154,166-167`; ansible 2.9.27 `lib/ansible/module_utils/basic.py:755,1929-1939` (argument defaults are filled in before the merge, so they are never `None`) |
| **Why it matters** | On every restart, a service still running 10 s after SIGTERM is SIGKILLed with its in-flight work (heat-engine, cinder copies, glance uploads); for `nova_libvirt` this matters only if libvirtd has not exited by then ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)). [NOT AVAILABLE] Whether services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`) receive SIGTERM at all ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)). The release note claiming 60 s (`releasenotes/notes/docker-stop-timeout-c8089f6bf92d6c28.yaml`) has no effect |

<a id="f4"></a>

### F4 — Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`

| | |
|---|---|
| **Finding** | **Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`.** Only absent images are pulled; an explicit `pull` is required |
| **Evidence** | [CODE] `kolla_docker.py:805-808`, `:403-413` |
| **Why it matters** | Mutable tags create silent drift between hosts. A later unrelated `pull` turns into a mass recreate |

<a id="f5"></a>

### F5 — `reconfigure` = `deploy`

| | |
|---|---|
| **Finding** | **`reconfigure` = `deploy`** for 70 of the 72 roles that have a `tasks/reconfigure.yml` (67 via `import_tasks: deploy.yml`, plus congress, mongodb and nova-hyperv via `include_tasks: deploy.yml`; only swift and bifrost have their own logic). A reconfigure re-runs Keystone registration, DB creation/grants and the DB-sync bootstrap containers of most services. Neutron is the exception: with the default `neutron_enable_rolling_upgrade: "yes"`, `bootstrap_neutron` runs on `deploy` but is skipped on `reconfigure`, so a reconfigure re-runs Neutron's DB create/grant tasks but not its DB sync |
| **Evidence** | [CODE] `roles/*/tasks/reconfigure.yml`; `roles/neutron/tasks/bootstrap_service.yml:21-22,24-46`, `roles/neutron/defaults/main.yml:411`. One-shot containers counted from the code: `-t nova` starts 5 on `control01` when cell0 is mapped and the cell is unchanged (API DB sync, `map_cell0`, cell DB sync, `list_cells` ×2: `roles/nova/tasks/bootstrap.yml:52-54`, `map_cell0.yml:2-26`, `roles/nova-cell/tasks/bootstrap.yml:38-40`, `create_cells.yml:2-3`, `discover_computes.yml:5`); on `-t neutron reconfigure` with default flags the neutron role starts none (`roles/neutron/tasks/bootstrap_service.yml:21-22,41-42`, `group_vars/all.yml:677`). [NOT AVAILABLE] Totals for a run without a tag, which depend on the enabled services |
| **Why it matters** | A "reconfigure" can apply schema migrations if the image tag moved, for most services; for Neutron only with non-default flags: `enable_neutron_sfc` (the `bootstrap_neutron_sfc` container runs `neutron-db-manage --subproject networking-sfc … upgrade head` on every reconfigure) or `neutron_enable_rolling_upgrade: "no"` (full `bootstrap_neutron`). There is never a "config only" path except `genconfig` + `deploy-containers` |

<a id="f6"></a>

### F6 — Global inputs are rendered into per-host files

| | |
|---|---|
| **Finding** | **Global inputs are rendered into per-host files.** `enable_*` flags, RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files |
| **Evidence** | [CODE] `group_vars/all.yml:206,216`; `nova-cell/templates/nova.conf.j2`; `neutron/templates/neutron.conf.j2:119` (memcached list, shared by the OVS agent on computes); `common/tasks/config.yml:109-240` |
| **Why it matters** | Small central changes cause fleet-wide restarts |

<a id="f7"></a>

### F7 — `--list-tasks` cannot show what a tag runs

| | |
|---|---|
| **Finding** | **`--list-tasks` cannot show what a tag runs**, and `--list-hosts` shows 0 hosts for `&enable_*` plays |
| **Evidence** | [CODE] ansible 2.9.27 `lib/ansible/cli/playbook.py:145-147,180-185` (the listing walks the statically compiled play and resolves host patterns before any task runs), `lib/ansible/inventory/manager.py:425`; `site.yml:21-25` (the `enable_*` groups are created by `group_by` at run time); [list-tasks-nova.txt](listings/list-tasks-nova.txt) |
| **Why it matters** | Operators need `genconfig` or staging to predict a run |

<a id="f8"></a>

### F8 — `--limit` does not confine actions

| | |
|---|---|
| **Finding** | **`--limit` does not confine actions.** `delegate_to: groups[x][0]` runs work on hosts outside the limit. With `deploy --limit` set to a compute host, `control01` (the first `neutron-server` and `nova-conductor` host of the `multinode` inventory) runs the Neutron DB create/grant and the `bootstrap_neutron` container, plus cell discovery (`nova_list_cells`, `openstack compute service list`, `nova-manage cell_v2 discover_hosts`). The nova-cell RabbitMQ user/vhost creation is also delegated (to the first RabbitMQ host), but it runs only when the first nova-conductor is inside the limit, so a limit to compute hosts does not run it |
| **Evidence** | [CODE] `site.yml:761-775` and `nova.yml:117-126` (both plays include `compute`); `roles/neutron/tasks/bootstrap.yml:12-13,31-32`, `bootstrap_service.yml:19-22`; `roles/nova-cell/tasks/wait_discover_computes.yml:41-42,86-89`, `discover_computes.yml:4-21`, `get_cell_settings.yml:2-16`; `roles/nova-cell/tasks/rabbitmq.yml:10-12`; `inventory/multinode:3-5,138-139,290-291,312-313` |
| **Why it matters** | "Only the new compute" still executes DB-sync containers on a controller |

<a id="f9"></a>

### F9 — With `--limit`, all hosts' facts are gathered sequentially

| | |
|---|---|
| **Finding** | **With `--limit`, all hosts' facts are gathered sequentially** by the limited hosts (delegated loop) |
| **Evidence** | [CODE] `gather-facts.yml:29-50`; loop items run one after another (ansible 2.9.27 `lib/ansible/executor/task_executor.py:317,367`) |
| **Why it matters** | O(total hosts) serial latency on every limited run without fact caching |

<a id="f10"></a>

### F10 — `kolla_serial` makes `run_once` steps repeat per batch

| | |
|---|---|
| **Finding** | **`kolla_serial` makes `run_once` steps repeat per batch** (API DB sync ×3 with serial 1 and the three controllers of the `multinode` inventory) and orders a play's restarts by host-pattern order (computes before conductors in the nova-cell play) |
| **Evidence** | [CODE] ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:161-169,257`, `lib/ansible/plugins/strategy/linear.py:288,315-316`, `lib/ansible/inventory/manager.py:411,428`; `roles/nova/tasks/bootstrap_service.yml:4-23`; `nova.yml:29-39,119-126`; `inventory/multinode:3-7,138-139,287-288` ([Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)) |
| **Why it matters** | Batching reduces blast radius but multiplies bootstrap work, and exposes ordering within a play |

<a id="f11"></a>

### F11 — The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides

| | |
|---|---|
| **Finding** | **The `openvswitch_agent.ini` merge** includes the operator's `ml2_conf.ini` overrides |
| **Evidence** | [CODE] `roles/neutron/tasks/config.yml:172-190` |
| **Why it matters** | Server-side ML2 changes restart every OVS agent |

<a id="f12"></a>

### F12 — The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes`

| | |
|---|---|
| **Finding** | **The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start** when `enable_neutron_agent_ha: yes`; its comment says this removes all L3 namespaces (what the command does is neutron code: [NOT AVAILABLE]) |
| **Evidence** | [CODE] `neutron-l3-agent-wrapper.sh.j2:5-12` |
| **Why it matters** | [NOT AVAILABLE] Whether an L3 agent restart interrupts router traffic on that node ([Q4](../troubleshooting/open-questions.md#q4)) |

<a id="f13"></a>

### F13 — The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes

| | |
|---|---|
| **Finding** | **The Nova deploy order** puts nova-compute before OVS and the Neutron agents on new computes |
| **Evidence** | [CODE] `site.yml:710-780` |
| **Why it matters** | [NOT AVAILABLE] Whether instances can be scheduled on such a compute before the later plays finish ([Execution flow §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)); relevant when adding computes one by one |

<a id="f14"></a>

### F14 — `kolla_set_configs --check` has blind spots

| | |
|---|---|
| **Finding** | **`kolla_set_configs --check` has blind spots.** It compares only the `config_files` entries of `config.json` (content, mode, owner). A change confined to `config.json` itself (`command`, `permissions`; all of memcached's settings) is never detected. A newly added optional file makes it exit 2, which fails `check-containers`, unless an entry listed before it already differs (then 1). `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run. A restart never removes the files of a dropped entry |
| **Evidence** | [CODE] kolla `docker/base/set_configs.py:60-65,131-151,160-235,310-330,388-393,407-432`; `kolla_docker.py:566-578` ([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)) |
| **Why it matters** | "`genconfig` + `--check`" ([Predict and inspect a run](../operations/predict-a-run.md)) under-reports some changes and over-reports others. A `config.json`-only change is applied by a normal deploy/reconfigure, because the changed template task notifies the restart handler. Once `genconfig` has written it, neither `deploy-containers` nor a later run (its template task is then unchanged) applies it until the container restarts for another reason |

<a id="f15"></a>

### F15 — What the bootstrap containers run differs per image

| | |
|---|---|
| **Finding** | **What the bootstrap containers run differs per image.** Nova's bootstrap containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`). Placement's `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure. Heat's does not re-apply a changed `heat_domain_admin_password` to Keystone. neutron-server's migrates `neutron-dynamic-routing`, which the rolling `upgrade` never migrates |
| **Evidence** | [CODE] kolla `docker/nova/nova-api/extend_start.sh:9-25`, `docker/nova/nova-conductor/extend_start.sh:3-17`, `docker/placement/placement-api/extend_start.sh:5-9`, `docker/heat/heat-api/extend_start.sh:5-17`, `docker/neutron/neutron-server/extend_start.sh:5-12,34-38`; `roles/nova/tasks/bootstrap_service.yml:13`, `roles/nova-cell/tasks/bootstrap_service.yml:11`, `roles/placement/tasks/bootstrap_service.yml:11`, `roles/heat/tasks/bootstrap_service.yml:11,21`, `roles/neutron/defaults/main.yml:412` |
| **Why it matters** | What a "reconfigure" or a tag-changing "deploy" does to databases depends on the image, not only on kolla-ansible ([Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)) |

## Related

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and bugs
  found in `ussuri-eol`
- [Open questions](../troubleshooting/open-questions.md) — [Q1–Q14](../troubleshooting/open-questions.md#q1), among them
  [Q4](../troubleshooting/open-questions.md#q4), which F12 refers to
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Risk register](../risk/risk-register.md) — the risks [R1–R25](../risk/risk-register.md#r1)
- [Kolla images](../concepts/kolla-images.md) — the image side of F14 and F15, and the answer to
  [Q14](../troubleshooting/open-questions.md#q14)
- [Per-role fact sheets](factsheets/index.md) — errata with their evidence
