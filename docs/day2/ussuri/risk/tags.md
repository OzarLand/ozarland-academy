---
title: What a tag really executes
description: "How tags select work in Kolla-Ansible Ussuri and what each important tag executes: target hosts, containers that can restart, per-tag answers."
tags: [tags, handlers, loop-notify, serial, limit, nova, neutron, openvswitch, ovn, haproxy, keystone, chrony, iscsi, reconfigure]
remember:
  - "A tag name does not describe the work a run performs: handlers are never filtered by tags, which is why <code>-t keystone</code> can restart HAProxy. <span class=\"ev ev-code\">CODE</span>"
  - "Loop-notify: with the default Nova settings, a nova-compute-only override restarts <code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code> on every compute host. <span class=\"ev ev-code\">CODE</span>"
  - "A tag never restricts which hosts a play targets; use <code>--limit</code> for that."
  - "<code>-t common</code> is a no-op; to push fluentd, cron or kolla_toolbox changes, use <code>-t chrony</code>, which reaches every host by default, or a service tag. <span class=\"ev ev-code\">CODE</span>"
  - "<code>--list-tasks</code> is not usable for Kolla; to predict restarts, use <code>genconfig</code> plus <code>kolla_set_configs --check</code>. <span class=\"ev ev-code\">CODE</span>"
scenarios:
  - title: "Try a nova-compute change on a few computes first"
    situation: "Your cloud has 40 computes. You changed an override in <code>/etc/kolla/config/nova/nova-compute.conf</code> and want it applied to 4 computes only, as a first step. A colleague says: \"Just run <code>reconfigure -t nova-cell</code>: the tag only picks the hosts that need it.\""
    ask: "What would you do?"
    choices:
      - text: "Run <code>kolla-ansible reconfigure -t nova --limit</code> on the 4 computes, straight away."
        verdict: "risky"
        why: "<code>--limit</code> does restrict the hosts, but on those hosts loop-notify still restarts <code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code> <span class=\"ev ev-code\">CODE</span>, and <code>-t nova</code> also runs <code>common</code> on them. Whether live migrations in progress fail and whether running VMs survive is <span class=\"ev ev-na\">NOT AVAILABLE</span>. For <code>nova</code> the page says: only with batching and a window; prefer <code>genconfig</code> + <code>deploy-containers --limit</code>."
      - text: "Run <code>genconfig</code>, predict the restarts with <code>kolla_set_configs --check</code>, then apply with <code>deploy-containers --limit</code> on the 4 computes, in a window."
        verdict: "best"
        why: "To predict restarts, use <code>genconfig</code> plus <code>kolla_set_configs --check</code>: <code>--list-tasks</code> cannot show the tasks inside roles, and <code>--check</code> is no substitute <span class=\"ev ev-code\">CODE</span>. For <code>nova</code> the page says: only with batching and a window; prefer <code>genconfig</code> + <code>deploy-containers --limit</code>."
      - text: "Run <code>kolla-ansible reconfigure -t nova-cell</code> as suggested, without <code>--limit</code>."
        verdict: "avoid"
        why: "A tag never restricts which hosts a play targets; use <code>--limit</code> for that. <code>nova-cell</code> touches every compute, and with the default Nova settings a nova-compute-only override restarts <code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code> on every compute host <span class=\"ev ev-code\">CODE</span>."
    see: "31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites"
  - title: "Push a common config change to every host"
    situation: "You need to push a change of the common config (fluentd, cron logrotate, kolla_toolbox) to every host of the cloud. A colleague suggests <code>-t common</code>, since that is the name of the role."
    ask: "What would you do?"
    choices:
      - text: "Run <code>kolla-ansible reconfigure -t common</code>, as your colleague suggests."
        verdict: "avoid"
        why: "<code>-t common</code> is a no-op <span class=\"ev ev-code\">CODE</span>: the include runs, but no task inside the included file does. It does not reconfigure fluentd, cron or kolla_toolbox."
      - text: "Run an untagged <code>reconfigure</code> of the whole cloud."
        verdict: "risky"
        why: "An untagged run also reaches the common config, but it runs all plays on all hosts: every container can restart, with all bootstrap/DB-sync containers and the Keystone registration of all services. The page calls it the full blast radius."
      - text: "Run <code>kolla-ansible reconfigure -t chrony</code>, with the VIP up."
        verdict: "best"
        why: "<code>-t chrony</code> reaches every host (chrony runs everywhere by default) and runs <code>common</code> + chrony there; it can restart only chrony, fluentd, cron and kolla_toolbox. The page rates it safe and the cheapest way to push common config fleet-wide; its prerequisite is the VIP up for the chrony clients."
    see: "4-practical-consequences"
quiz:
  - q: "Why can <code>-t keystone</code> restart HAProxy?"
    options: ["Because handlers ignore tags", "Because the keystone role depends on the haproxy role"]
    answer: 0
    explain: "Handlers ignore tags <span class=\"ev ev-code\">CODE</span>."
    see: "22-handlers-ignore-tags-code"
  - q: "Does a tag restrict which hosts a play targets?"
    options: ["Yes, a tag selects the hosts of its service", "No: use <code>--limit</code> for that"]
    answer: 1
    explain: "A tag never restricts which hosts a play targets; use <code>--limit</code> for that."
    see: "4-practical-consequences"
  - q: "Does any play of the <code>nova-api</code> tag target compute hosts?"
    options: ["Yes", "No"]
    answer: 1
    explain: "<code>nova</code> and <code>nova-cell</code> target the computes; <code>nova-api</code> does not."
    see: "3-what-a-tag-really-executes-master-table"
---

# What a tag really executes

How tags actually select work in Kolla-Ansible Ussuri, and what each important tag executes. Read [Repository
architecture §3–4](../concepts/repository-architecture.md#3-anatomy-of-siteyml) first for the play and role skeleton.

> [!NOTE]
> **Key answers**
>
> - **What a tag executes, on which hosts, and which containers can restart:** the master table
>   ([§3](#3-what-a-tag-really-executes-master-table)). Config files, running VMs, API availability, networking and
>   storage, safety and prerequisites per tag:
>   [§3.1](#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites).
> - **Which tags reach the computes:** `nova`, `nova-cell`, `neutron`, `openvswitch`, `ovn`, `chrony` and `iscsi` target
>   compute hosts, as do `baremetal` (`bootstrap-servers`, all hosts) and `nova-reload`/`nova-cell-reload` (work only on
>   `upgrade`); `nova-api` does not touch computes ([§3](#3-what-a-tag-really-executes-master-table)).
> - **Loop-notify:** a change that concerns one container restarts every container of that role on that host. With the
>   default Nova settings, a nova-compute-only override restarts `nova_compute`, `nova_libvirt` and `nova_ssh` on every
>   compute host [CODE] ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
> - **`-t common` is a no-op** [CODE] ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code)). To push fluentd,
>   cron or kolla_toolbox changes, use `-t chrony`, which reaches every host by default, or a service tag
>   ([§4](#4-practical-consequences)).
> - **Handlers ignore tags:** this is why `-t keystone` can restart HAProxy [CODE]
>   ([§2.2](#22-handlers-ignore-tags-code)).
> - **A tag never restricts which hosts a play targets; use `--limit` for that.** `--skip-tags haproxy` skips the entire
>   haproxy play ([§4](#4-practical-consequences)).

> **The single most important rule:** a tag name does **not** describe the work a run performs. What runs depends on:
>
> - which plays carry or inherit the tag;
> - the `common` role reaching each host for the first time;
> - the haproxy play's per-service includes;
> - handlers, which are **never filtered by tags**;
> - Ansible 2.9's loop-notify semantics.
>
> Everything below is read from the source; nothing was run against a host. The evidence labels **[CODE]** and
> **[NOT AVAILABLE]** are defined once, in [Evidence labels](../start/conventions.md#evidence-labels).

---

## 1. Where tags are defined

| Source | Example (evidence) | Inherited by |
|---|---|---|
| **Play-level tags** | `haproxy` play: `tags: [haproxy]` (`site.yml:132-133`). All 10 plays of `nova.yml`, e.g. `tags: [nova, nova-cell, nova-cell-deploy, nova-cell-upgrade]` (`nova.yml:127-131`) | every task of the play, including role dependencies (`common`) and statically imported roles |
| **Role-level tags** in `roles:` | `- { role: neutron, tags: neutron, when: … }` (`site.yml:777-780`). memcached has `tags: [memcache, memcached]` (`:489`) | every task of the role, **including its meta dependency `common`** |
| **Task-level tags on `include_role`** | haproxy block: `include_role: {name: nova, tasks_from: loadbalancer}` with `tags: [nova, nova-api]` (`site.yml:293-299`) | the include statement only; see [§2.3](#23-include_role--tags-always-inside-the-haproxy-play-code) |
| **`tags: always`** | gather-facts and group_by plays (`gather-facts.yml:21,50`, `site.yml:95`). `import_role: haproxy-config` in 48 of the 49 `loadbalancer.yml` files. nova-cell's `loadbalancer.yml` reaches it through `import_tasks: proxy_loadbalancer.yml` → looped `include_tasks: cell_proxy_loadbalancer.yml` → `import_role`, with `tags: always` at every level (`roles/nova-cell/tasks/loadbalancer.yml:21,57,93`). `congress/tasks/register.yml:8` | runs regardless of `--tags`, unless the enclosing dynamic include is skipped |
| **Tags inside roles** | `common/tasks/main.yml:3,9` (`tags: common`). `nova/tasks/stop.yml:7` (`tags: nova`). `service-rabbitmq/tasks/main.yml:43` (`tags: [service-rabbitmq]`) | – |
| **Other playbooks** | `kolla-host.yml:10` (`baremetal`), `mariadb_backup.yml:6`, `mariadb_recovery.yml:6` (`mariadb`), `bifrost.yml:6` (`bifrost`) | – |

The full per-play tag list is generated in [Generated inventory
§1](../reference/generated-inventory.md#1-plays-executed-by-siteyml-in-order). Per-service cards (tags, task flow,
handlers, node types) are in [Components](../components/index.md). The output of `ansible-playbook --list-tags` against
the real `site.yml` is in [list-tags-site.txt](../reference/listings/list-tags-site.txt). Per play it shows the *task
tags* after inheritance; note that **`common` appears in almost every play**.

---

## 2. Ansible 2.9 semantics that Kolla relies on

### 2.1 Dynamic `include_tasks` and tag inheritance [CODE]

Every role starts with `include_tasks: "{{ kolla_action }}.yml"` (dynamic). In Ansible 2.9, tasks inside a
dynamically included file:

- **do inherit** the tags of the enclosing *role* and *play*: `nova`, `neutron`, `chrony`, `haproxy`, …;
- **do not inherit** tags written on the `include_tasks` statement itself (they apply to the include only, unless
  `apply:` is used — Kolla never uses `apply:`).

In the source (ansible 2.9.27): without `apply:`, the include itself becomes the parent of the included blocks
(`lib/ansible/playbook/task_include.py:135-154`, used at `lib/ansible/plugins/strategy/__init__.py:936-944`). An
include is not statically loaded (`task_include.py:56`), so `Block._get_parent_attribute` skips it and takes the tags
of the include's own parent, of the role and its dependency chain, and of the play
(`lib/ansible/playbook/block.py:311-326, :329-360`). The included tasks are then filtered on those tags
(`lib/ansible/plugins/strategy/linear.py:371`, `block.py:378-380`). Applied to Kolla's `common` role, whose
`include_tasks` and `set_fact` carry `tags: common` (`roles/common/tasks/main.yml:1-10`) and whose task files carry
no other tag:

```text
--tags common  → the include_tasks runs, but no task inside the included file does (none carries `common`)
--tags nova    → the common tasks DO run (inherited play tag), then the service tasks
--tags chrony  → the common tasks run in the chrony play (first play the host appears in)
```

The code that drops the include's own tags is identical in Ansible 2.8.20 [CODE]: `Task._get_parent_attribute`,
`Block._get_parent_attribute` and `TaskInclude.build_parent_block` (ansible 2.8.20
`lib/ansible/playbook/task.py:427-458`, `block.py:300-364`, `task_include.py:124-143`) match 2.9.27's
`task.py:458-489`, `block.py:300-364` and `task_include.py:135-154`.

### 2.2 Handlers ignore tags [CODE]

A notified handler runs even if its own tags do not match `--tags`. Only the play's task blocks are filtered on tags
(ansible 2.9.27 `lib/ansible/playbook/play.py:256-283`, `lib/ansible/executor/play_iterator.py:186-189`); handlers run
for every notified host with no tag check (`lib/ansible/plugins/strategy/__init__.py:972-988`). This is why
`-t keystone` can restart HAProxy: the `haproxy-config` task under `tags: always` notifies `Restart haproxy container`
(`roles/haproxy-config/tasks/main.yml:20-21`, handler at `roles/haproxy/handlers/main.yml:2`; [fact sheet A
§1.9][sheet-a-19]).

### 2.3 `include_role` + `tags: always` inside (the haproxy play) [CODE]

The haproxy play's per-service `include_role` statements are dynamic too. Their own tags (`keystone`, `nova`, …)
only select the include statement: the included role's blocks get the `include_role` as parent (ansible 2.9.27
`lib/ansible/playbook/role_include.py:99, :104-106`), which is skipped as in
[§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), while `tags: always` matches any `--tags`
(`lib/ansible/playbook/taggable.py:66-68`). For the work inside to run, 48 of the 49 `loadbalancer.yml` files wrap a
single `import_role: haproxy-config` with `tags: always` (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`). nova-cell's
file reaches the same role through `import_tasks: proxy_loadbalancer.yml`, a looped `include_tasks:
cell_proxy_loadbalancer.yml` and then `import_role` (`cell_proxy_loadbalancer.yml:3-12`), with `tags: always` at every
level, so the effect is the same. Net effect: `-t <svc>` runs that service's haproxy config on all haproxy hosts.

### 2.4 Loop notify: one changed item notifies the handlers of all items [CODE]

Ansible 2.9.27 `lib/ansible/plugins/strategy/__init__.py:616-623`:

```python
for result_item in result_items:
    if '_ansible_notify' in result_item:
        if task_result.is_changed():          # <- aggregate status of the WHOLE loop
            for handler_name in result_item['_ansible_notify']:
                ... notify handler_name
```

`_ansible_notify` is attached to every executed (non-skipped) loop item (ansible 2.9.27
`lib/ansible/executor/task_executor.py:790`). The loop result is changed if any item changed
(`task_executor.py:116-121`, `lib/ansible/executor/task_result.py:96-106`). If *any* item changed, the templated
handler name of *every* executed item is notified. Kolla's `config.yml` and `check-containers.yml` loop over
`<role>_services` with `notify: "Restart {{ item.key }} container"`. So **a change that concerns one container
restarts every container of that role on that host.** Skipped items do not notify: an item whose `when` is false
returns before `_ansible_notify` is set (`task_executor.py:557-559`).

Applied to the real playbook [CODE]. An override that only touches `/etc/kolla/config/nova/nova-compute.conf` changes
only nova-compute's `nova.conf` (`roles/nova-cell/tasks/config.yml:63-82`; `defaults/main.yml:349-355`).
`kolla_set_configs --check` in `nova_compute` then exits 1 (kolla `docker/base/set_configs.py:32-35`, `:54-55`,
`:166-171`, `:231-235`, `:427-429`), so the `Check nova-cell containers` loop reports changed
(`library/kolla_docker.py:326-332`, `:568-569`; `roles/nova-cell/tasks/check-containers.yml:2-20`). Its executed items
on a compute host with the defaults (`group_vars/all.yml:682, :726, :966`) are `nova-libvirt`, `nova-ssh` and
`nova-compute` (`roles/nova-cell/defaults/main.yml:3-54`), so the handlers restart `nova_compute`, **`nova_libvirt` and
`nova_ssh`** on every compute host.

A scheduler-only override changes the nova role's `Copying over nova.conf` loop, whose executed items on a `multinode`
controller are `nova-api` and `nova-scheduler` (`roles/nova/tasks/config.yml:51-69`; `nova-super-conductor` needs
`enable_cells`, default `no`, `group_vars/all.yml:595`), so it restarts `nova_api` *and* `nova_scheduler`.

Impact analysis in [Operations](../operations/index.md).

Ussuri supports only Ansible 2.8–2.9 (`tools/kolla-ansible:58-59`). The code is **identical on Ansible 2.8.20**
[CODE]: the block above is ansible 2.8.20 `lib/ansible/plugins/strategy/__init__.py:540-557`, the same as 2.9.27's
`:609-626`, and 2.8.20 sets `_ansible_notify` the same way (`lib/ansible/executor/task_executor.py:784`). Newer
Ansible is irrelevant to Ussuri and is not covered.

### 2.5 `run_once` with `serial` [CODE]

With `kolla_serial` > 0, a `run_once` task runs once **per batch**, not once per play: each batch is a separate run of
the play (ansible 2.9.27 `lib/ansible/executor/playbook_executor.py:161-169`), and `run_once` only ends the host loop
inside that run (`lib/ansible/plugins/strategy/linear.py:288, :315-316`). This applies to bootstrap containers, Keystone
registration and DB creation. It is not harmful for idempotent steps, but it multiplies the number of DB-sync containers
and Keystone API calls ([fact sheet C, cross-cutting table][sheet-c-0]).

With `kolla_serial=1` and the three controllers of the `multinode` inventory (`inventory/multinode:3-7`,
`:138-139`, `:286-287`) [CODE]:

- `nova_api_bootstrap` (`run_once`, no `delegate_to`, `roles/nova/tasks/bootstrap_service.yml:4-23`) runs 3 times,
  once per controller batch, and each time on that batch's host (once more when `map_cell0` reports changed,
  `map_cell0.yml:25-26`).
- `map_cell0` (`run_once`, `roles/nova/tasks/map_cell0.yml:22`) runs 3 times.
- The compute registration wait plus `list_cells` run once per batch that holds a compute: they are gated on the batch's
  first compute and delegated to the first conductor (`roles/nova-cell/tasks/wait_discover_computes.yml:41-42, :89`;
  `discover_computes.yml:5, :21`; `deploy.yml:24-42`).
- Nova containers restart strictly one host at a time, since each one-host batch finishes before the next starts.

### 2.6 `--list-tasks` is not usable for Kolla [CODE]

Because of [§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), `ansible-playbook site.yml --list-tasks -t nova`
lists only `include_tasks` placeholders for each role: the listing walks only the statically compiled play (ansible
2.9.27 `lib/ansible/cli/playbook.py:180-185`), while dynamic includes are loaded at run time
(`lib/ansible/plugins/strategy/linear.py:360`). `common`'s inner tasks, `config.yml` and `check-containers.yml` are
invisible ([list-tasks-nova.txt](../reference/listings/list-tasks-nova.txt)). Plays whose host pattern depends on the
`group_by` groups (`&enable_nova_True`) also resolve to **0 hosts** at list time. Those groups are created at run time
(`[WARNING]: Could not match supplied host pattern, ignoring: enable_nova_True`, listing line 5), and an `&` pattern
keeps only the hosts that match it (`lib/ansible/inventory/manager.py:423-425`). `--check` is no substitute:
`kolla_docker` does not declare check-mode support, so Ansible skips it under `--check` [CODE]
(`kolla_docker.py:1031-1035`; ansible 2.9.27 `lib/ansible/module_utils/basic.py:1595-1596`), and whether such a run is
usable is [NOT AVAILABLE] ([Predict and inspect a run](../operations/predict-a-run.md), [Open questions
Q9](../troubleshooting/open-questions.md#q9)). To predict restarts, use `genconfig` plus `kolla_set_configs --check`
(end of [§3.1](#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites)).

---

## 3. What a tag really executes (master table)

"Target hosts" assumes the Ussuri `multinode` example inventory. "Containers" lists those that *can* be restarted or
recreated, **only if** a config, parameter or image change is detected: a restart handler runs only when a task that
notifies it reports *changed* ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) [CODE].
The notifying tasks are the config tasks and `check-containers`, whose `compare_container` reports *changed* only when
the container is missing, is not running, differs from the task in a compared parameter (image, volumes, environment,
dimensions, command, privileges, …), or `kolla_set_configs --check` exits 1 or 137 or meets a Docker client error
(`kolla_docker.py:326-350, :480-484, :543-578`) [CODE]. [NOT AVAILABLE] Whether, on an unchanged cloud and apart
from the exception below, every task that notifies a restart handler reports *ok*, so that nothing restarts.

The kolla source shows one exception: `kolla_set_configs --check` exits 1 on every run for a `config_files` entry with
`preserve_properties` and no `perm`, and in practice for a directory source that contains subdirectories (kolla
`docker/base/set_configs.py:173-178, :193-204`; [Kolla images
§3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)). So
`prometheus_server` restarts on every deploy/reconfigure whenever `{{ node_custom_config }}/prometheus/extras/` holds
files already copied into the container (`roles/prometheus/templates/prometheus-server.json.j2:10-15`). A newly added
extras file makes `--check` exit 2 instead: the check task fails on that host before the handlers run, and the container
is not restarted (`roles/prometheus/tasks/deploy.yml:4-9`; [Predict and inspect a run](../operations/predict-a-run.md)).
Later runs fail the same way, because the file is still not in the container, until `prometheus_server` restarts for
another reason.

"common" means the `common` role runs on every host of the first matching play (fluentd/cron/kolla_toolbox config +
container check). Apart from the `common`, `service-rabbitmq` and `baremetal` rows, every role below except memcached
has `common` as a meta dependency. A tag that selects a haproxy include can also restart `haproxy` if that frontend
changed ([§2.2](#22-handlers-ignore-tags-code)).

| Tag | Plays / roles selected | Tasks executed | Target hosts | Containers that can restart | Other side effects | Potential impact |
|---|---|---|---|---|---|---|
| *(no tag)* | all 84 plays | everything for `kolla_action` | all | all | all bootstrap/DB-sync containers, Keystone registration of all services | Full blast radius |
| `common` | include + `set_fact` in each play | **nothing else** [CODE] (`roles/common/tasks/main.yml:1-10`, [§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code)) | all (no-op) | none | sets `common_run=True` | **No-op.** It does *not* reconfigure fluentd/cron/toolbox |
| `haproxy` | haproxy play: `common`, haproxy role (config-host, config, check-containers), all 49 loadbalancer includes evaluated, but only those of enabled services run (each except placement's has a `when` on `enable_*` flags, `site.yml:139-389`, so the number depends on those flags) | sysctl, `ip_vs`, `haproxy.cfg`, `keepalived.conf`, certs, the `services.d/*.cfg` of every enabled service | haproxy hosts | `haproxy`, `keepalived`, `fluentd`/`cron`/`kolla_toolbox` (via common) | – | API and DB path interruption if anything changed; whether the VIP moves is [NOT AVAILABLE] ([A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour)) |
| `<svc>` (e.g. `keystone`, `glance`, `cinder`, `heat`, `placement`; `horizon` differs, see below the table) | haproxy play (that service's include only) + the service play | haproxy `services.d/<svc>*.cfg`; `common` on the service hosts; register, config, check-containers, bootstrap of the service | haproxy hosts + service hosts | haproxy (if its frontend changed), all of the service's containers on a host if any changed ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)), common containers | DB sync container, Keystone registration | Service API outage during the parallel restart; HAProxy restart if the frontend changed |
| `nova` | haproxy (nova + nova-cell includes), all 10 `nova.yml` plays | API/cell0/cell DB bootstrap, cell create/update, nova + nova-cell config/check, discovery, scheduler SIGHUP; reload/online-migration plays are no-ops except on `upgrade` | haproxy, `nova-api`, `nova-scheduler`, `nova-conductor`, consoles, **every `compute`** | nova API/scheduler/conductor/console proxies, **nova_compute, nova_libvirt, nova_ssh on all computes**, common containers | 5 one-shot container runs on `control01` when cell0 is mapped and the cell is unchanged (API DB sync, map_cell0, cell DB sync, list_cells ×2) [CODE] (`roles/nova/tasks/bootstrap.yml:52-54`, `roles/nova-cell/tasks/bootstrap.yml:39-41`, `create_cells.yml:2`, `discover_computes.yml:5`); RabbitMQ vhost/user for the cell; `kill -HUP` of nova_scheduler on every scheduler | See [Nova deep dive](../components/nova-deep-dive.md), [Reconfigure Nova](../operations/reconfigure-nova.md) |
| `nova-api` | haproxy nova include, API DB bootstrap play, nova play, scheduler cell-cache refresh, API reload/migrations | haproxy-config for the nova API/metadata frontends; `common` on nova-api and nova-scheduler hosts; nova_api + nova_cell0 DB/user creation, API DB sync and `map_cell0` on `nova-api[0]`; nova role: Keystone registration, config, check-containers, flush; scheduler SIGHUP | controllers + haproxy | nova_api, nova_scheduler, nova_super_conductor, fluentd/cron/kolla_toolbox (via common) | API DB sync, map_cell0 | Does **not** touch computes |
| `nova-cell` | haproxy nova-cell include, cell DB bootstrap, nova-cell play, cell reload/migrations | haproxy-config for the console-proxy frontends; `common` on conductors, console hosts and computes; on the first conductor: cell DB/user, RabbitMQ vhost/user (gated on the first conductor but run via `delegate_to` on the first host of the cell RPC/notify group, `rabbitmq[0]` by default), cell DB sync, cell create/update; nova-cell role: config-host (`br_netfilter`, sysctl), config, check-containers, flush, then compute discovery delegated to the first conductor | conductors, consoles, **all computes** | nova_conductor, consoles, nova_compute, nova_libvirt, nova_ssh, fluentd/cron/kolla_toolbox (via common, on conductors, consoles and every compute) | cell DB sync, cell create/update, RabbitMQ vhost/user for the cell, discovery | Touches every compute |
| `nova-bootstrap`, `nova-api-bootstrap`, `nova-cell-bootstrap` | the two bootstrap plays (`nova.yml:29-96`); their `include_role` of nova / nova-cell also pulls in the `common` meta dependency | `common`, then DB creation, DB sync containers, cell mapping | `common`: all `nova-api` hosts (API play) and all `nova-conductor` hosts (cell play); DB tasks and one-shot containers: `nova-api[0]`, `nova-conductor[0]` | fluentd/cron/kolla_toolbox (via common) [CODE] (`include_role` compiles the role with its dependencies: ansible 2.9.27 `lib/ansible/playbook/role_include.py:104`, `lib/ansible/playbook/role/__init__.py:448-451`); no nova service; one-shot bootstrap containers | RabbitMQ vhost/user for the cell | Schema changes only if images are newer |
| `nova-reload`, `nova-api-reload`, `nova-cell-reload` | reload plays (`nova.yml:164-225`) | `recreate_or_restart` of nova services **only when `kolla_action == upgrade`** | as named | on upgrade: all nova services | – | No-op outside upgrade |
| `nova-online-data-migrations` (+ `-api-`, `-cell-`) | `nova.yml:230-272` | `nova-manage db online_data_migrations` | `nova-api[0]`, `nova-conductor[0]` | – | upgrade only | – |
| `nova-refresh-scheduler-cell-cache` | `nova.yml:140-156` (`import_role: nova`, which pulls in the `common` dependency) | `common` (if not yet run on the host in this run), then `kill -HUP` of `nova_scheduler` (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:10`) | nova-scheduler hosts | `nova_scheduler` only gets SIGHUP (no restart); fluentd/cron/kolla_toolbox (via common) when the tag is used alone | – | Runs on **every** deploy/reconfigure with `nova` or `nova-api`, where common has already run, so it adds only the signal ([list-tasks-nova.txt](../reference/listings/list-tasks-nova.txt) play #37) |
| `neutron` | haproxy neutron include, neutron play (hosts include **`compute`** and `manila-share`) | register, config-host (sysctl, modules), config, check-containers, DB and DB-user creation (every deploy and reconfigure), `bootstrap_neutron` DB-sync container (deploy only while `neutron_enable_rolling_upgrade` keeps its default `yes`, `bootstrap_service.yml:21-22`) | haproxy, neutron-server, network agent hosts, **every compute** | neutron_server, all agents on a host if any changed ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)), common | – | OVS agent restarts on computes, L3/DHCP agent restarts on network nodes; [NOT AVAILABLE] whether flows are resynced and traffic is interrupted ([Reconfigure Neutron](../operations/reconfigure-neutron.md)) |
| `openvswitch` | openvswitch play | module load, config, check-containers, **post-config** (`ovs-vsctl set … system-id`, bridge ensure) | `openvswitch` group (network + **compute**) | `openvswitch_db`, `openvswitch_vswitchd`, fluentd/cron/kolla_toolbox (via common) | `Set system-id` reports *changed* on every run | [NOT AVAILABLE] whether a vswitchd restart interrupts **all VM traffic** on that host ([Risk register R7](risk-register.md#r7)) |
| `ovn` | ovn play | config, check-containers, chassis bootstrap (`ovs-vsctl` × ~5 per host) | OVN DB hosts, **every compute and network** | ovn NB/SB DB, northd, ovn-controller, fluentd/cron/kolla_toolbox (via common) | overwrites `ovn-cms-options` | [A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable) |
| `mariadb` | haproxy mariadb include, mariadb play (no serial) | cluster lookup, config, check, rolling restart handlers | mariadb hosts | mariadb (modulo-4 waves), clustercheck, fluentd/cron/kolla_toolbox (via common) | – | [B §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb) |
| `rabbitmq` | haproxy include, **both** rabbitmq plays (`rabbitmq` and `outward-rabbitmq` share the tag) | haproxy-config for the `rabbitmq_management` frontend; `common`; config (`config.json`, `rabbitmq-env.conf`, `rabbitmq.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`), check-containers, volume creation and, only for a new volume, the `rabbitmq_bootstrap` container; flush | rabbitmq hosts | rabbitmq (one by one), fluentd/cron/kolla_toolbox (via common) | – | [B §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice) |
| `memcached` / `memcache` | memcached play (`memcache` does **not** select the haproxy include) | config dir + `config.json`, check-containers. No `common` and no flush: the restart handler runs at the end of the play. `memcached` also selects the haproxy include, which renders a frontend only with `enable_haproxy_memcached` (default `no`) | memcached hosts | memcached (all at once) | – | [NOT AVAILABLE] whether the restart empties the token cache and the Horizon sessions kept there ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) |
| `chrony` | chrony play (first play for **every** host) | `common` + chrony on all hosts | **all hosts** | chrony, fluentd, cron, kolla_toolbox | – | The cheapest way to reconfigure `common` fleet-wide ([§4](#4-practical-consequences)) |
| `iscsi` | iscsi play | `common`; config-host (load and persist `configfs`), config dirs + `config.json`, check-containers, flush | iscsid (compute + storage), tgtd | iscsid, tgtd, fluentd/cron/kolla_toolbox (via common) | – | Volume attach path on computes ([D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)) |
| `service-rabbitmq` | the RabbitMQ user/vhost blocks inside roles | **nothing** on its own (inside dynamic includes) | – | – | – | Not usable as a selector |
| `baremetal` | `kolla-host.yml` only | host preparation | all | **Docker daemon restart if `daemon.json` changed** | packages, users, `/etc/hosts` | [E §1–3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#1-ansiblekolla-hostyml-the-bootstrap-servers-command) |

`horizon` follows the `<svc>` row without registration and, by default, without bootstrap. The role has no
`register.yml`, so it is never registered in Keystone. Its DB creation and `bootstrap_horizon` DB sync run only when
`horizon_backend_database` is true (default `{{ enable_murano | bool }}`, `group_vars/all.yml:982`;
`roles/horizon/tasks/deploy.yml:10-11`). With defaults, `-t horizon` runs the haproxy horizon include, `common`,
config, check-containers and, if anything changed, the horizon restart handler.

### 3.1 Per-tag answers: files, VMs, APIs, networking/storage, safety, prerequisites

This table answers the remaining per-tag questions. What runs, which services are affected and which containers can
restart are in the master table above. Which handlers can fire is in [§5](#5-role--handler-map-core-services): handlers
fire only on drift, and tags never filter them ([§2.2](#22-handlers-ignore-tags-code)). "R*n*" refers to [Risk
register](risk-register.md). Everything assumes a change was detected. [NOT AVAILABLE] Whether, apart from the exception
given in [§3](#3-what-a-tag-really-executes-master-table), no tag restarts anything on an unchanged cloud. A "none" or
"none directly" under Running VMs or Networking / storage means that the tag cannot restart `nova_compute`,
`nova_libvirt`, `nova_ssh`, an Open vSwitch, OVN or Neutron agent container, `iscsid` or `tgtd` [CODE]; whether its
restarts reach running VMs or traffic another way is [NOT AVAILABLE] ([Limits of the
study](../reference/method-and-limits.md#limits-of-this-study)).

| Tag | Config files that can change | Running VMs | API availability | Networking / storage | Safe on its own? | Prerequisites |
|---|---|---|---|---|---|---|
| `haproxy` | `haproxy.cfg`, `services.d/*.cfg` of enabled services, `keepalived.conf`, TLS PEMs, sysctl; common files | no direct effect; [NOT AVAILABLE] whether instance metadata requests, which the metadata agents send to nova through the VIP (`roles/neutron/templates/metadata_agent.ini.j2:4`), fail while HAProxy is down | **yes**: HAProxy restarts (never reloads) on all haproxy hosts at once, and all APIs and the DB path go through it; [NOT AVAILABLE] whether established connections are cut and whether keepalived drops or moves the VIP ([R8](risk-register.md#r8)) | control plane only | yes if nothing reports a change, since the restart handlers then never run [CODE] ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)); with a change, batch with `ANSIBLE_SERIAL=1 … reconfigure` | facts of every backend host; certificates if TLS is on |
| `<svc>` API service (`keystone`, `glance`, `cinder`, `heat`, `placement`, `horizon`) | service configs on its hosts, its `services.d` frontend, common files | none for keystone/heat/placement/horizon; glance/cinder transfers in progress are SIGKILLed after 10 s ([R24](risk-register.md#r24)) | **yes**: the service restarts on all its hosts at once; [NOT AVAILABLE] whether other APIs fail authentication while Keystone restarts ([R19](risk-register.md#r19)) and whether scheduling stops while Placement restarts ([Nova deep dive §3](../components/nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate) item 4) | cinder: volume operations; `iscsid` and `tgtd` are in the `iscsi` play, not under `-t cinder` (`site.yml:512-521`) | yes, it is the intended unit; it still runs Keystone registration and DB sync (horizon: neither, by default); batch with `ANSIBLE_SERIAL`; the glance file backend has one host ([R20](risk-register.md#r20)) | MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP |
| `nova` | API and cell `nova.conf`, `config.json`, policy, libvirt (`libvirtd.conf`, `qemu.conf`, SASL), nova-ssh files, Ceph keyrings when enabled, nova frontends, common files | [CODE] `nova_libvirt` restarts with any nova-cell drift on a compute (loop-notify, [R1](risk-register.md#r1)); [NOT AVAILABLE] whether live migrations in progress fail and whether running VMs survive ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), [Reconfigure Nova §5](../operations/reconfigure-nova.md#5-running-vms-live-migration-scheduling)) | nova API, scheduler and conductors restart at once; [NOT AVAILABLE] whether instance actions fail meanwhile | [NOT AVAILABLE] whether attach/detach and port binding in flight fail; no OVS change | only with batching and a window; prefer `genconfig` + `deploy-containers --limit` ([Write config first, apply in controlled batches §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)) | MariaDB, RabbitMQ, memcached, Keystone, Placement, Glance, Neutron registered |
| `nova-api` | API-side `nova.conf`, `config.json`, policy, nova frontends, common files on controllers | none | nova API, scheduler, super-conductor | none | yes; does not touch computes | as `nova` |
| `nova-cell` | cell `nova.conf`, libvirt, nova-ssh and Ceph files on computes and conductors, console frontends, common files | **yes**, as `nova` | conductors and console proxies | as `nova` | as `nova` | the API DB and cell0 mapping (`nova-api`/`nova`), RabbitMQ |
| `neutron` | `neutron.conf`, `ml2_conf.ini`, `openvswitch_agent.ini`, `l3_agent.ini`, `dhcp_agent.ini`, `metadata_agent.ini` (+ enabled features), neutron frontend, common files | **yes**: OVS agent restart on every compute ([NOT AVAILABLE] whether and how it resyncs flows, and whether traffic is lost), L3/DHCP/metadata agent restarts on network nodes; with `enable_neutron_agent_ha`, the L3 agent wrapper runs `neutron-netns-cleanup` before the agent starts, and what that command deletes is [NOT AVAILABLE] ([R6](risk-register.md#r6)) | neutron-server restarts on all controllers at once | **networking: yes** ([Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking)); storage: no | risky without batching ([R5](risk-register.md#r5), [R6](risk-register.md#r6)) | Open vSwitch or OVN running, MariaDB, RabbitMQ, Keystone |
| `openvswitch` | `config.json` of `openvswitch_db`/`openvswitch_vswitchd`, `start-ovs`, `start-ovsdb-server`; `system-id`, and bridges on network nodes (and on computes when `computes_need_external_bridge`), via `ovs-vsctl` | [NOT AVAILABLE] whether running VMs are affected if `openvswitch_vswitchd` restarts or is recreated, e.g. whether all VM traffic on the host stops until flows are reinstalled ([R7](risk-register.md#r7)). The kernel module stays loaded and `conf.db` keeps bridges and ports, but nothing saves or restores flows ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 13) | none | **networking: yes** | yes if unchanged (`Set system-id` reports *changed* without restarting); image changes per host batch | `openvswitch` kernel module |
| `ovn` | `config.json` of the OVN containers; chassis `external_ids` (`ovn-cms-options` overwritten) | [NOT AVAILABLE] whether an ovn-controller restart re-programs flows on the host | NB/SB DB restarts interrupt neutron-server's OVN driver | **networking: yes** | check manual `ovn-cms-options` first ([A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable)) | Open vSwitch |
| `mariadb` | `galera.cnf` (lists all nodes), `config.json`, clustercheck files, `wsrep-notify.sh` | none directly | rolling restart in 4 waves; HAProxy's single active backend (node 0) restarts in one of them, [NOT AVAILABLE] whether in the first ([R9](risk-register.md#r9)) | DB only | only on a healthy, fully synced cluster | every node `Synced` |
| `rabbitmq` | `rabbitmq.conf`, `rabbitmq-env.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`, `config.json` | none directly; [NOT AVAILABLE] whether nova-compute and the agents lose RPC while their broker restarts | restarts are one by one (`roles/rabbitmq/handlers/main.yml:6-26`); [NOT AVAILABLE] whether RPC-backed API calls time out meanwhile | none directly; [NOT AVAILABLE] whether the agents reconnect by themselves | yes on a healthy cluster; membership changes are [R3](risk-register.md#r3) | no partitions, all nodes running |
| `memcached` / `memcache` | `config.json` | none | memcached restarts on all memcached hosts at once; [NOT AVAILABLE] whether that empties the token cache (with extra load on Keystone) and loses the Horizon sessions kept in memcached ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) | none | yes, off-peak | none |
| `chrony` | `chrony.conf` and common files on **every** host | none | none (common containers only) | none | yes; also the cheapest way to push common config fleet-wide ([§4](#4-practical-consequences)) | VIP up for the chrony clients |
| `common` | none (no-op) [CODE] ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code)) | none | none | none | safe but does nothing | – |
| `iscsi` | `config.json` of `iscsid`/`tgtd`; `configfs` persistence | `iscsid`: [NOT AVAILABLE] whether existing sessions are kernel-held and whether attach/detach during the window fails. `tgtd` (LVM backend with `tgtadm`, the default target helper on Debian/Ubuntu) has no start script and empty `config_files`, and its command is a bare `tgtd`: nothing in its start path runs `tgt-admin` to load `/etc/tgt/targets.conf` (where the image adds `include /var/lib/cinder/volumes/*`). [NOT AVAILABLE] whether tgtd loads that file itself or keeps targets only in memory, and so whether a `tgtd` restart cuts disk I/O for VMs using LVM volumes from that host until the targets are re-created ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)) | none | **storage path on computes** ([D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)) | with care, per host batch | – |
| `baremetal` (`bootstrap-servers`) | `daemon.json`, `/etc/hosts`, packages, users | **yes** if `daemon.json` changes: the Docker restart stops every container, `nova_libvirt` and OVS included ([R14](risk-register.md#r14)) | yes on controllers | yes | no on a live host unless `daemon.json` is unchanged; use `--limit` | – |

Validation: `--list-tags` lists only the tags it can see statically
([list-tags-site.txt](../reference/listings/list-tags-site.txt)); tags that occur only inside dynamically included
files, such as `service-rabbitmq` (reached through `include_role: nova-cell, tasks_from: bootstrap`, `nova.yml:81-84`),
do not appear. `--list-tasks` cannot show the tasks inside roles, because they come from dynamic includes
([§2.6](#26---list-tasks-is-not-usable-for-kolla-code)). Use `genconfig` plus `docker exec -u root <c>
/usr/local/bin/kolla_set_configs --check` to predict restarts ([Predict and inspect a
run](../operations/predict-a-run.md); [Kolla images
§3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

---

## 4. Practical consequences

1. **"Only reconfigure `common`" is not possible with a tag.** `-t common` is a no-op [CODE]
   ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code)). Changes to fluentd, cron or kolla_toolbox config reach
   a host only when *some* service play that includes the host runs with matching tags, or with no tags:
   - `-t chrony` reaches every host (chrony runs everywhere by default);
   - `-t nova` reaches all nova hosts;
   - `-t neutron` reaches network and compute hosts.
2. **A service tag drags in shared infrastructure.**
   - `-t nova` also runs the haproxy play (nova frontends), `common` on every nova host and compute, Keystone
     registration and the DB bootstrap containers [CODE] (`site.yml:293-306`, `roles/nova/meta/main.yml:2-3`,
     `roles/nova-cell/meta/main.yml:2-3`, `nova.yml:117-135`, `roles/nova/tasks/deploy.yml:2`, `nova.yml:29-96`).
   - `-t neutron` also runs `common` on all computes.
   - A tag never restricts *which hosts* a play targets; use `--limit` for that.
3. **Handlers make the impact data-dependent.** The same command can be a no-op or a fleet-wide restart, depending
   on whether a rendered file changed. That in turn depends on *global* variables (`enable_*`, group membership,
   passwords), not only on the tagged service [CODE]: e.g. common's cron logrotate config lists services by their
   `enable_*` flags and notifies `Restart cron container` (`roles/common/tasks/config.yml:163-240`).
4. **`--skip-tags` can avoid the haproxy play.** `--skip-tags haproxy` skips the entire haproxy play, including the
   per-service includes ([fact sheet A §1.9][sheet-a-19]), while leaving the service play untouched. Combining `-t nova`
   with `--skip-tags haproxy` is valid. Most service tags (`keystone`, `glance`, `neutron`, `nova`, …) select both the
   service's haproxy include and the service play(s), so for a single-tag service such as keystone this is the tag-based
   way to drop the haproxy part. Some tags select no haproxy include at all:
   - `memcache` (only the memcached play);
   - nova's narrower play tags: `-t nova-bootstrap,nova-api-deploy,nova-cell-deploy,nova-refresh-scheduler-cell-cache`
     does what a `-t nova` deploy/reconfigure does, minus the haproxy includes (`site.yml:293-306`);
   - `chrony`, `openvswitch`, `ovn`, `iscsi` (one play each).
5. **Tags do not change `kolla_action` logic.** For a given tag, `deploy` and `reconfigure` execute the same tasks (e.g.
   `-t nova deploy` and `-t nova reconfigure`; [Repository architecture
   §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). Apart from swift and bifrost, whose
   `reconfigure.yml` has its own logic, the only role-level exception is Neutron's `bootstrap_neutron` DB-sync
   container, which runs on deploy only while `neutron_enable_rolling_upgrade` keeps its default `yes`; Neutron DB and
   DB-user creation run on both. The other difference is the `kolla_serial` pass-through ([Repository architecture
   §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook)).

---

## 5. Role → handler map (core services)

Handlers run in **definition order** after `meta: flush_handlers` (end of `deploy.yml`) or at the end of the play. All
use `kolla_docker` `recreate_or_restart_container` unless noted. The complete list for all roles is in [Generated
inventory §3](../reference/generated-inventory.md#3-role-task-structure-handlers-and-helper-role-usage).

| Role | Handlers (definition order) | Special logic | Evidence |
|---|---|---|---|
| common | Restart fluentd → Restart kolla-toolbox (→ Initializing toolbox: `docker exec … ansible --version`) → Restart cron | – | `roles/common/handlers/main.yml` |
| haproxy | Restart haproxy → Restart keepalived → Waiting for haproxy → Waiting for VIP | `wait_for` on the monitor port | [A §1.5](../reference/factsheets/a-infra-lb-ovn.md#15-handlers-ansibleroleshaproxyhandlersmainyml-definition-order--run-order-see-common-mechanics) |
| mariadb | Bootstrap MariaDB cluster (listen) … → Restart MariaDB on existing cluster members (`include_tasks restart_services.yml`, loop 0..3, `index % 4 == item`) → Start MariaDB on new nodes … | 4 restart waves, waiting for port + WSREP `Synced` | `roles/mariadb/handlers/main.yml:66-78`, [B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order) |
| rabbitmq | Restart rabbitmq: first node, then the others one by one | `rabbitmqctl wait` | [B §2.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#25-handlers-ansiblerolesrabbitmqhandlersmainyml-in-definition-order) |
| keystone | (Init keystone database upgrade, upgrade only) → Restart keystone-ssh → Restart keystone-fernet → Restart keystone → (Finish keystone database upgrade, upgrade only) | all hosts at once | `roles/keystone/handlers/main.yml:5-95`, [B §3.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#35-handlers-ansibleroleskeystonehandlersmainyml-order-is-load-bearing-comment-2-3) |
| nova | Restart nova-super-conductor → nova-scheduler → nova-api | skipped on upgrade when `nova_safety_upgrade` | `roles/nova/handlers/main.yml` |
| nova-cell | Restart nova-conductor → novncproxy → spicehtml5proxy → serialproxy → nova-ssh → **nova-libvirt** (retries 5; notifies Create libvirt SASL user) → Create libvirt SASL user → nova-compute → nova-compute-ironic → fake → Wait for nova-compute services (upgrade only, 30 s pause) | libvirt is restarted **before** nova-compute | `roles/nova-cell/handlers/main.yml:1-196` |
| neutron | one handler per agent/server | none | `roles/neutron/handlers/main.yml` |
| openvswitch | Restart openvswitch-db-server (→ Waiting for openvswitch_db) → Restart openvswitch-vswitchd | – | `roles/openvswitch/handlers/main.yml:1-42` |

## Related

- [Operations](../operations/index.md) (impact of each scenario, commands)
- [Risk register](risk-register.md) (risks [R1–R25](risk-register.md#r1))
- [Components](../components/index.md)
- [Tag index](tag-index.md) (tag index)

[sheet-a-19]: ../reference/factsheets/a-infra-lb-ovn.md#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy
[sheet-c-0]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#0-cross-cutting-facts-apply-to-all-five-roles
