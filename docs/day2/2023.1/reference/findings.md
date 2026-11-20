---
title: Technical findings
description: The fifteen headline findings of the source study, F1 to F15, re-checked against 2023.1-eol, each with its evidence, status and why it matters.
tags: [evidence, loop-notify, tags, limit, serial, images, kolla-set-configs, one-shot, reconfigure, nova, neutron, docker]
remember:
  - "Restart blast radius is per role-on-host, not per container: a nova-compute-only change restarts <code>nova_libvirt</code> and <code>nova_ssh</code>. <span class=\"ev ev-code\">CODE</span>"
  - "Same-tag image rebuilds are not picked up by <code>deploy</code>/<code>reconfigure</code>/<code>upgrade</code>: only absent images are pulled; an explicit <code>pull</code> is required. <span class=\"ev ev-code\">CODE</span>"
  - "A <code>reconfigure</code> is a <code>deploy</code>: it applies schema migrations if the image tag moved, for Neutron too. <span class=\"ev ev-code\">CODE</span>"
  - "<code>--limit</code> does not confine actions: \"only the new compute\" still executes DB-sync containers on a controller. <span class=\"ev ev-code\">CODE</span>"
  - "A service still running 60 s after SIGTERM is killed with its in-flight work; raising <code>docker_graceful_timeout</code> now has an effect. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "In 2023.1, a config change touches one nova-compute container only. Which containers of that host can restart?"
    options: ["Every container of that role on that host: a nova-compute-only change restarts <code>nova_libvirt</code> and <code>nova_ssh</code>", "Only the container whose config changed"]
    answer: 0
    explain: "Loop-notify amplification still holds in 2023.1 <span class=\"ev ev-code\">CODE</span>: when one item of a config/check loop changes, ansible-core 2.14 notifies the handlers of all executed items. Restart blast radius is per role-on-host, not per container."
    see: "f1--loop-notify-amplification"
  - q: "In 2023.1, what does <code>-t common</code> do?"
    options: ["Nothing: it is a no-op, because tags on the dynamic <code>include_tasks</code> do not propagate", "It renders the common configs and restarts what changed"]
    answer: 1
    explain: "F2 no longer holds in 2023.1 <span class=\"ev ev-code\">CODE</span>: <code>common</code> is a play of its own, with play-level <code>tags: common</code>, so <code>-t common</code> renders the common configs and restarts what changed. A service tag (e.g. <code>-t nova</code>) skips it."
    see: "f2---t-common-is-a-no-op"
  - q: "In 2023.1, does <code>reconfigure</code> run Neutron's DB sync?"
    options: ["No: <code>bootstrap_neutron</code> runs on <code>deploy</code> but is skipped on <code>reconfigure</code>", "Only when <code>enable_neutron_sfc</code> is set", "Yes: <code>bootstrap_neutron</code> is imported without any condition and runs on every <code>deploy</code> and <code>reconfigure</code>"]
    answer: 2
    explain: "The Ussuri Neutron exception is gone <span class=\"ev ev-code\">CODE</span>: <code>bootstrap_neutron</code> runs on every <code>deploy</code> and <code>reconfigure</code>, and <code>neutron_enable_rolling_upgrade</code> is read only by <code>upgrade.yml</code>. A reconfigure applies schema migrations if the image tag moved, for Neutron too."
    see: "f5--reconfigure--deploy"
---

# Technical findings

The study consolidates three things. This page holds the first:

1. what was established and how (evidence level): the headline findings below;
2. implementation limitations and bugs found in `2023.1-eol`: [Known bugs and
   limitations](../troubleshooting/known-bugs-and-limitations.md);
3. what the sources do not establish: [Open questions](../troubleshooting/open-questions.md) and [What is not
   known](../troubleshooting/what-is-not-known.md).

> [!NOTE]
> **Key answers**
>
> - **Fifteen headline findings ([F1–F15](#f1))**, first established on `ussuri-eol` and re-checked against
>   `2023.1-eol`, each with its evidence and why it matters ([Headline findings](#headline-findings)).
> - **Still hold in 2023.1:** loop-notify amplification ([F1](#f1)), same-tag image rebuilds ([F4](#f4)),
>   `reconfigure` = `deploy` ([F5](#f5), now including Neutron's DB sync), [F6](#f6) to [F10](#f10), [F12](#f12),
>   [F13](#f13), and per-image bootstrap behaviour ([F15](#f15)).
> - **No longer hold in 2023.1:** the `-t common` no-op ([F2](#f2): `common` is its own tagged play), the ignored stop
>   timeout ([F3](#f3): the 60 s `docker_graceful_timeout` reaches `docker stop` through a systemd unit) and the
>   `ml2_conf.ini` merge into `openvswitch_agent.ini` ([F11](#f11)). [F14](#f14) changed in part.

Evidence levels: **[CODE]** and **[NOT AVAILABLE]**, defined once, in [Evidence
labels](../start/conventions.md#evidence-labels). The study rests only on reading source code; no run against a host is
used as evidence.

## Headline findings

| # | Finding |
|---|---|
| [F1](#f1) | Loop-notify amplification |
| [F2](#f2) | `-t common` is a no-op (no longer holds in 2023.1) |
| [F3](#f3) | `docker_graceful_timeout` and `docker_client_timeout` are ignored (no longer holds in 2023.1) |
| [F4](#f4) | Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade` |
| [F5](#f5) | `reconfigure` = `deploy` |
| [F6](#f6) | Global inputs are rendered into per-host files |
| [F7](#f7) | `--list-tasks` cannot show what a tag runs |
| [F8](#f8) | `--limit` does not confine actions |
| [F9](#f9) | With `--limit`, all hosts' facts are gathered sequentially |
| [F10](#f10) | `kolla_serial` makes `run_once` steps repeat per batch |
| [F11](#f11) | The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides (no longer holds in 2023.1) |
| [F12](#f12) | The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes` |
| [F13](#f13) | The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes |
| [F14](#f14) | `kolla_set_configs --check` has blind spots (changed in part in 2023.1) |
| [F15](#f15) | What the bootstrap containers run differs per image |

<a id="f1"></a>

### F1 — Loop-notify amplification

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **Loop-notify amplification.** When a config/check task loops over a role's services and *one* item changes, ansible-core 2.14 notifies the handlers of *all* executed items. In Kolla this means a change for one container restarts every container of that role on that host. A nova-compute-only change restarts `nova_libvirt` and `nova_ssh`; a scheduler-only change restarts `nova_api`; a change on a network node restarts all neutron agents there |
| **Evidence** | [CODE] ansible-core 2.14.18 `lib/ansible/plugins/strategy/__init__.py:614-621`, `lib/ansible/executor/task_executor.py:124-128,804-805`; `roles/nova-cell/tasks/check-containers.yml:2-22`, `roles/nova/tasks/config.yml:64-82`, `roles/neutron/tasks/check-containers.yml:2-19`; walk-through in [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) |
| **Why it matters** | Restart blast radius is per *role-on-host*, not per container. libvirt restarts far more often than operators expect |

<a id="f2"></a>

### F2 — `-t common` is a no-op

**No longer holds in 2023.1** [CODE]. `common` is a play of its own, with play-level `tags: common`
(`site.yml:86-97`), and no role has a `meta/` directory, so nothing else reaches the role. The included tasks inherit
the play tag, so `-t common` renders the common configs and restarts what changed.

| | |
|---|---|
| **Finding** | **Ussuri:** `-t common` was a no-op, because tags on the dynamic `include_tasks` do not propagate to the included tasks. **2023.1:** `roles/common/tasks/main.yml:1-2` is a bare `include_tasks: "{{ kolla_action }}.yml"`, reached only from the `Apply role common` play; `-t common` runs it on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` hosts, and a service tag (e.g. `-t nova`) skips it |
| **Evidence** | [CODE] `site.yml:86-97`; `roles/common/tasks/main.yml:1-2`; ansible-core 2.14.18 `lib/ansible/playbook/task_include.py:131-150`, `lib/ansible/playbook/block.py:297-368`, `lib/ansible/plugins/strategy/linear.py:311` ([Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code); [R25](../risk/risk-register.md#r25)) |
| **Why it matters** | `common` changes (fluentd/cron/toolbox) are applied by `-t common` or by an untagged run, and never by a service-tagged run: a fluentd/logrotate change made when enabling a service with `-t <svc> deploy` waits for the next run of the common play ([R2](../risk/risk-register.md#r2)) |

<a id="f3"></a>

### F3 — `docker_graceful_timeout` and `docker_client_timeout` are ignored

**No longer holds in 2023.1** [CODE]. The two options have no argument default any more, so the values from
`docker_common_options` are used; containers (except one-shots) run under a systemd unit whose `ExecStop` carries the
graceful timeout ([R24](../risk/risk-register.md#r24)).

| | |
|---|---|
| **Finding** | **Ussuri:** the `kolla_docker` argument defaults (10 s, 120 s) overrode `common_options`, so every stop sent SIGKILL 10 s after SIGTERM. **2023.1:** `graceful_timeout` and `client_timeout` are declared without a default, so the `common_options` values (`docker_graceful_timeout: 60`, `docker_client_timeout: 120`) are taken; the 10 s and 120 s values apply only when neither is given. A restart or stop goes through the unit `kolla-<name>-container.service`, whose `ExecStop` is `docker stop <name> -t <graceful_timeout>`; without a unit file the module calls Docker `stop` with the same timeout |
| **Evidence** | [CODE] `library/kolla_docker.py:303,325,351-382`; `group_vars/all.yml:105,139-140,152-153`; `module_utils/kolla_systemd_worker.py:20-39,63-73`; `module_utils/kolla_docker_worker.py:436-452` |
| **Why it matters** | A service still running 60 s after SIGTERM is killed with its in-flight work (heat-engine, cinder copies, glance uploads); raising `docker_graceful_timeout` now has an effect (it reaches the unit on the next restart, [R24](../risk/risk-register.md#r24)). For `nova_libvirt` this matters only if libvirtd has not exited by then ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)). [NOT AVAILABLE] systemd's own stop timeout for these units (the unit sets none). [NOT AVAILABLE] Whether services started by a shell wrapper that does not `exec` them (e.g. `neutron-l3-agent`, `haproxy`) receive SIGTERM at all ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)) |

<a id="f4"></a>

### F4 — Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **Same-tag image rebuilds are not picked up by `deploy`/`reconfigure`/`upgrade`.** Only absent images are pulled; an explicit `pull` is required |
| **Evidence** | [CODE] `module_utils/kolla_docker_worker.py:116-132` (the container's image id is compared with the local image of that tag), `:362-388` (`check_image`, then `pull_image` only when the image is absent) ([R13](../risk/risk-register.md#r13)) |
| **Why it matters** | Mutable tags create silent drift between hosts. A later unrelated `pull` turns into a mass recreate |

<a id="f5"></a>

### F5 — `reconfigure` = `deploy`

**Holds in 2023.1, without the Neutron exception** [CODE].

| | |
|---|---|
| **Finding** | **`reconfigure` = `deploy`** for 57 of the 59 roles that have a `tasks/reconfigure.yml` (56 via `import_tasks: deploy.yml`, plus skyline via `include_tasks: deploy.yml`; only swift and bifrost have their own logic). A reconfigure re-runs Keystone registration, DB creation/grants and the DB-sync bootstrap containers of the services. The Ussuri Neutron exception is gone: `bootstrap_neutron` is imported without any condition and runs on every `deploy` and `reconfigure`; `neutron_enable_rolling_upgrade` is read only by `upgrade.yml` |
| **Evidence** | [CODE] `roles/*/tasks/reconfigure.yml`; `roles/neutron/tasks/bootstrap.yml:38`, `roles/neutron/tasks/bootstrap_service.yml:2-21`, `roles/neutron/tasks/upgrade.yml:4-8`, `roles/neutron/defaults/main.yml:710` ([Repository architecture §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). One-shot containers counted from the code: `-t nova` starts 6 on `control01` when cell0 is mapped and the cell is unchanged (API DB sync, `map_cell0`, `list_cells` ×3 — the cell0 lookup new in 2023.1, `create_cells` and `discover_computes` —, cell DB sync: `roles/nova/tasks/bootstrap.yml:54-56`, `roles/nova/tasks/map_cell0.yml:2-30,63-67`, `roles/nova-cell/tasks/bootstrap.yml:41-43`, `create_cells.yml:2-4`, `discover_computes.yml:4-5,21`, `get_cell_settings.yml:2-21`); on `-t neutron reconfigure` the neutron role starts one, `bootstrap_neutron`, on the first `neutron-server` host (`roles/neutron/tasks/bootstrap_service.yml:20-21`). [NOT AVAILABLE] Totals for a run without a tag, which depend on the enabled services |
| **Why it matters** | A "reconfigure" applies schema migrations if the image tag moved, for Neutron too (`neutron-db-manage … upgrade head` for neutron and each enabled subproject, kolla `docker/neutron/neutron-server/extend_start.sh:5-13`; the separate Ussuri `bootstrap_neutron_sfc` container no longer exists). There is never a "config only" path except `genconfig` + `deploy-containers` (`tools/kolla-ansible:485-487,540-542`) |

<a id="f6"></a>

### F6 — Global inputs are rendered into per-host files

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **Global inputs are rendered into per-host files.** `enable_*` flags, RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files |
| **Evidence** | [CODE] `group_vars/all.yml:212,222` (`rpc_transport_url`, `notify_transport_url`: every RabbitMQ host, user and password); `nova-cell/templates/nova.conf.j2`; `neutron/templates/neutron.conf.j2:125` (memcached list, shared by the OVS agent on computes); `common/tasks/config.yml:77-209` (`td-agent.conf` and `logrotate.conf` from the global `enable_*` flags) |
| **Why it matters** | Small central changes cause fleet-wide restarts |

<a id="f7"></a>

### F7 — `--list-tasks` cannot show what a tag runs

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **`--list-tasks` cannot show what a tag runs**, and `--list-hosts` shows 0 hosts for `&enable_*` plays |
| **Evidence** | [CODE] ansible-core 2.14.18 `lib/ansible/cli/playbook.py:168-171,202-207` (the listing walks the statically compiled play and resolves host patterns before any task runs), `lib/ansible/inventory/manager.py:447-449`; `site.yml:16-20` (the `enable_*` groups are created by `group_by` at run time); [list-tasks-nova.txt](listings/list-tasks-nova.txt) |
| **Why it matters** | Operators need `genconfig` or staging to predict a run |

<a id="f8"></a>

### F8 — `--limit` does not confine actions

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **`--limit` does not confine actions.** `delegate_to: groups[x][0]` runs work on hosts outside the limit. With `deploy --limit` set to a compute host, `control01` (the first `neutron-server` and `nova-conductor` host of the `multinode` inventory) runs the Neutron DB create/grant and the `bootstrap_neutron` container, plus cell discovery (`nova_list_cells`, `openstack compute service list`, `nova-manage cell_v2 discover_hosts`). The nova-cell RabbitMQ user/vhost creation is also delegated (to the first RabbitMQ host), but it runs only when the first nova-conductor is inside the limit, so a limit to compute hosts does not run it |
| **Evidence** | [CODE] `site.yml:590-605` and `nova.yml:117-136` (both plays include `compute`); `roles/neutron/tasks/bootstrap.yml:13-14,33-34`, `roles/neutron/tasks/bootstrap_service.yml:20-21`; `roles/nova-cell/tasks/wait_discover_computes.yml:8-43,87-90`, `discover_computes.yml:4-23`, `get_cell_settings.yml:2-21`; `roles/nova-cell/tasks/rabbitmq.yml:10-12`; `inventory/multinode:3-5,117-118,266-267,288-289` ([Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node)) |
| **Why it matters** | "Only the new compute" still executes DB-sync containers on a controller |

<a id="f9"></a>

### F9 — With `--limit`, all hosts' facts are gathered sequentially

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **With `--limit`, all hosts' facts are gathered sequentially** by the limited hosts (delegated loop) |
| **Evidence** | [CODE] `gather-facts.yml:30-54` (each limited host loops over its share of `groups['all']`; skipped for hosts that already have facts); loop items run one after another (ansible-core 2.14.18 `lib/ansible/executor/task_executor.py:287-335`) ([R23](../risk/risk-register.md#r23)) |
| **Why it matters** | O(total hosts) serial latency on every limited run without fact caching |

<a id="f10"></a>

### F10 — `kolla_serial` makes `run_once` steps repeat per batch

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **`kolla_serial` makes `run_once` steps repeat per batch** (API DB sync ×3 with serial 1 and the three controllers of the `multinode` inventory) and orders a play's restarts by host-pattern order (computes before conductors in the nova-cell play) |
| **Evidence** | [CODE] ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:181-190`, `lib/ansible/plugins/strategy/linear.py:217,247-248`, `lib/ansible/inventory/manager.py:400-412,429-450`; `roles/nova/tasks/bootstrap_service.yml:2-21`; `nova.yml:29-51,117-136`; `inventory/multinode:3-7,117-118,263-264` ([Tags §2.5](../risk/tags.md#25-run_once-with-serial-code)) |
| **Why it matters** | Batching reduces blast radius but multiplies bootstrap work, and exposes ordering within a play |

<a id="f11"></a>

### F11 — The `openvswitch_agent.ini` merge includes the operator's `ml2_conf.ini` overrides

**No longer holds in 2023.1** [CODE]. `ml2_conf.ini` is rendered only for `neutron-server` and
`neutron-infoblox-ipam-agent`; `openvswitch_agent.ini` has its own template and override files
([R5](../risk/risk-register.md#r5)).

| | |
|---|---|
| **Finding** | **Ussuri:** the `openvswitch_agent.ini` merge included the operator's `ml2_conf.ini` overrides. **2023.1:** `openvswitch_agent.ini` merges `templates/openvswitch_agent.ini.j2` with `neutron/openvswitch_agent.ini` and `neutron/<host>/openvswitch_agent.ini` only |
| **Evidence** | [CODE] `roles/neutron/tasks/config.yml:158-178` (`services_need_ml2_conf_ini`), `:197-212` (`openvswitch_agent.ini`) |
| **Why it matters** | Server-side ML2 changes no longer restart every OVS agent; they restart `neutron_server`, and through loop-notify every neutron container on a host that also runs neutron-server ([F1](#f1), [R5](../risk/risk-register.md#r5)). OVS agent options belong in `neutron/openvswitch_agent.ini` |

<a id="f12"></a>

### F12 — The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start when `enable_neutron_agent_ha: yes`

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **The L3 agent wrapper runs `neutron-netns-cleanup --force --agent-type l3` at start** when `enable_neutron_agent_ha: yes` (default `no`); its comment says this removes all L3 namespaces (what the command does is neutron code: [NOT AVAILABLE]) |
| **Evidence** | [CODE] `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-11`; `group_vars/all.yml:721` |
| **Why it matters** | [NOT AVAILABLE] Whether an L3 agent restart interrupts router traffic on that node ([Q4](../troubleshooting/open-questions.md#q4)). 2023.1 adds `neutron_l3_agent_failover_delay` to space the restarts across hosts when set above its default `0` (`roles/neutron/defaults/main.yml:633`) ([R6](../risk/risk-register.md#r6)) |

<a id="f13"></a>

### F13 — The Nova deploy order puts nova-compute before OVS and the Neutron agents on new computes

**Still holds in 2023.1** [CODE].

| | |
|---|---|
| **Finding** | **The Nova deploy order** puts nova-compute before OVS and the Neutron agents on new computes |
| **Evidence** | [CODE] `site.yml:544` (`import_playbook: nova.yml`, whose `Apply role nova-cell` play is `nova.yml:117-136`), then `site.yml:546-555` (`Apply role openvswitch`) and `site.yml:590-608` (`Apply role neutron`) |
| **Why it matters** | [NOT AVAILABLE] Whether instances can be scheduled on such a compute before the later plays finish ([Execution flow §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)); relevant when adding computes one by one |

<a id="f14"></a>

### F14 — `kolla_set_configs --check` has blind spots

**Holds in 2023.1, changed in part** [CODE]: a missing optional destination is now drift (exit 1), and a restart now
removes most dropped entries.

| | |
|---|---|
| **Finding** | **`kolla_set_configs --check` has blind spots.** It compares only the `config_files` entries of `config.json` (content, mode, owner). A change confined to `config.json` itself (`command`, `permissions`; all of memcached's settings) is never detected, nor is an entry dropped from `config.json`. A newly added optional file now reports drift (exit 1), like any missing destination; the Ussuri exit 2 is gone. `preserve_properties` entries (prometheus extras) and directory sources with subdirectories report drift on every run. A restart now removes (or resets to the original) the destination of a dropped entry when it was recorded at the container's first start; glob sources are never recorded and keep their stale files |
| **Evidence** | [CODE] kolla `docker/base/set_configs.py:64-72,165-198,200-218,220-242,452-474,502,516-532,556-559,562-582`; `module_utils/kolla_docker_worker.py:155-190`; `roles/memcached/templates/memcached.json.j2:2-3` ([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)) |
| **Why it matters** | "`genconfig` + `--check`" ([Predict and inspect a run](../operations/predict-a-run.md)) under-reports some changes and over-reports others. A `config.json`-only change is applied by a normal deploy/reconfigure, because the changed template task notifies the restart handler. Once `genconfig` has written it, neither `deploy-containers` nor a later run (its template task is then unchanged) applies it until the container restarts for another reason |

<a id="f15"></a>

### F15 — What the bootstrap containers run differs per image

**Still holds in 2023.1; the Neutron gap is closed** [CODE].

| | |
|---|---|
| **Finding** | **What the bootstrap containers run differs per image.** Nova's bootstrap containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`). Placement's `KOLLA_BOOTSTRAP` container also runs `online_data_migrations`, on every deploy/reconfigure. Heat's does not re-apply a changed `heat_domain_admin_password` to Keystone. neutron-server's migrates neutron and each enabled subproject; the Ussuri gap (`neutron-dynamic-routing` migrated by the bootstrap but never by the rolling `upgrade`) is closed, because both lists are the enabled `neutron_subprojects` |
| **Evidence** | [CODE] kolla `docker/nova/nova-api/extend_start.sh:9-30`, `docker/nova/nova-conductor/extend_start.sh:3-17`, `docker/placement/placement-api/extend_start.sh:5-9`, `docker/heat/heat-api/extend_start.sh:5-17`, `docker/neutron/neutron-server/extend_start.sh:5-13,17-34`; `roles/nova/tasks/bootstrap_service.yml:11`, `roles/nova-cell/tasks/bootstrap_service.yml:11`, `roles/placement/tasks/bootstrap_service.yml:11`, `roles/heat/tasks/bootstrap_service.yml:11,22`, `roles/neutron/defaults/main.yml:656-664,705,711` |
| **Why it matters** | What a "reconfigure" or a tag-changing "deploy" does to databases depends on the image, not only on kolla-ansible ([Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run)) |

## Related

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) — implementation limitations and bugs
  found in `2023.1-eol`
- [Open questions](../troubleshooting/open-questions.md) — [Q1–Q14](../troubleshooting/open-questions.md#q1), among them
  [Q4](../troubleshooting/open-questions.md#q4), which F12 refers to
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Risk register](../risk/risk-register.md) — the risks [R1–R25](../risk/risk-register.md#r1)
- [Kolla images](../concepts/kolla-images.md) — the image side of F14 and F15, and the answer to
  [Q14](../troubleshooting/open-questions.md#q14)
- [Per-role fact sheets](factsheets/index.md) — errata with their evidence
