---
title: What a tag really executes
description: "How tags select work in Kolla-Ansible 2023.1 and what each important tag executes: target hosts, containers that can restart, per-tag answers."
tags: [tags, handlers, loop-notify, serial, limit, nova, neutron, openvswitch, ovn, haproxy, loadbalancer, keystone, chrony, iscsi, reconfigure]
remember:
  - "A tag name does not describe the work a run performs: handlers are never filtered by tags, which is why <code>-t keystone</code> can restart HAProxy. <span class=\"ev ev-code\">CODE</span>"
  - "Loop-notify: with the default Nova settings, a nova-compute-only override restarts <code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code> on every compute host. <span class=\"ev ev-code\">CODE</span>"
  - "A tag never restricts which hosts a play targets; use <code>--limit</code> for that."
  - "<code>-t common</code> now does the work: <code>common</code> is its own play, and a service tag no longer runs it, so fluentd, cron and kolla_toolbox changes need <code>-t common</code> or an untagged run. <span class=\"ev ev-code\">CODE</span>"
  - "<code>--list-tasks</code> is not usable for Kolla; to predict restarts, use <code>genconfig</code> plus <code>kolla_set_configs --check</code>. <span class=\"ev ev-code\">CODE</span>"
scenarios:
  - title: "Try a nova-compute change on a few computes first"
    situation: "Your cloud has 40 computes. You changed an override in <code>/etc/kolla/config/nova/nova-compute.conf</code> and want it applied to 4 computes only, as a first step. A colleague says: \"Just run <code>reconfigure -t nova-cell</code>: the tag only picks the hosts that need it.\""
    ask: "What would you do?"
    choices:
      - text: "Run <code>kolla-ansible reconfigure -t nova-cell</code> as suggested, without <code>--limit</code>."
        verdict: "avoid"
        why: "A tag never restricts which hosts a play targets; use <code>--limit</code> for that. <code>nova-cell</code> touches every compute, and with the default Nova settings a nova-compute-only override restarts <code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code> on every compute host <span class=\"ev ev-code\">CODE</span>."
      - text: "Run <code>kolla-ansible reconfigure -t nova --limit</code> on the 4 computes, straight away."
        verdict: "risky"
        why: "<code>--limit</code> does restrict the hosts, but on those hosts loop-notify still restarts <code>nova_compute</code>, <code>nova_libvirt</code> and <code>nova_ssh</code> <span class=\"ev ev-code\">CODE</span>, and whether live migrations in progress fail and whether running VMs survive is <span class=\"ev ev-na\">NOT AVAILABLE</span>. For <code>nova</code> the page says: only with batching and a window; prefer <code>genconfig</code> + <code>deploy-containers --limit</code>."
      - text: "Run <code>genconfig</code>, predict the restarts with <code>kolla_set_configs --check</code>, then apply with <code>deploy-containers --limit</code> on the 4 computes, in a window."
        verdict: "best"
        why: "To predict restarts, use <code>genconfig</code> plus <code>kolla_set_configs --check</code>: <code>--list-tasks</code> cannot show the tasks inside roles, and <code>--check</code> is no substitute <span class=\"ev ev-code\">CODE</span>. For <code>nova</code> the page says: only with batching and a window; prefer <code>genconfig</code> + <code>deploy-containers --limit</code>."
    see: "31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites"
  - title: "Push a common config change to every host"
    situation: "You need to push a change of the common config (fluentd, cron logrotate, kolla_toolbox) to every host of the cloud. A colleague suggests <code>-t chrony</code>, because that tag used to reach every host."
    ask: "What would you do?"
    choices:
      - text: "Run <code>kolla-ansible reconfigure -t common</code>, with <code>ANSIBLE_SERIAL</code> set if you want batches."
        verdict: "best"
        why: "Reconfiguring <code>common</code> is <code>-t common</code> in 2023.1: <code>common</code> is its own play and no service play runs it <span class=\"ev ev-code\">CODE</span>. It runs on every host of the <code>common</code> group, every host at once unless <code>ANSIBLE_SERIAL</code> is set, and its containers are not on the VM or API path. The page calls it the way to push common config fleet-wide."
      - text: "Run <code>kolla-ansible reconfigure -t chrony</code>, as your colleague suggests."
        verdict: "avoid"
        why: "<code>chrony</code> no longer exists: 2023.1 has no chrony play and no chrony role, so the tag runs only the <code>always</code> plays (fact gathering, <code>group_by</code>). It is no longer a way to reach every host; use <code>-t common</code>."
      - text: "Run an untagged <code>reconfigure</code> of the whole cloud."
        verdict: "risky"
        why: "An untagged run also reaches the common config, but it runs all plays on all hosts: every container can restart, with all bootstrap/DB-sync containers and the Keystone registration of all services. The page calls it the full blast radius."
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

How tags actually select work in Kolla-Ansible 2023.1, and what each important tag executes. Read [Repository
architecture §3–4](../concepts/repository-architecture.md#3-anatomy-of-siteyml) first for the play and role skeleton.

> [!NOTE]
> **Key answers**
>
> - **What a tag executes, on which hosts, and which containers can restart:** the master table
>   ([§3](#3-what-a-tag-really-executes-master-table)). Config files, running VMs, API availability, networking and
>   storage, safety and prerequisites per tag:
>   [§3.1](#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites).
> - **Which tags reach the computes:** `nova`, `nova-cell`, `neutron`, `openvswitch`, `ovn` (through `ovn-controller`),
>   `iscsi` (when `iscsid` is enabled) and `common` target compute hosts, as do `baremetal` (`bootstrap-servers`, all
>   hosts) and `nova-reload`/`nova-cell-reload` (work only on `upgrade`); `nova-api` does not touch computes
>   ([§3](#3-what-a-tag-really-executes-master-table)). `chrony` no longer exists: 2023.1 has no chrony play.
> - **Loop-notify:** a change that concerns one container restarts every container of that role on that host. With the
>   default Nova settings, a nova-compute-only override restarts `nova_compute`, `nova_libvirt` and `nova_ssh` on every
>   compute host [CODE] ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
> - **`-t common` now does the work** [CODE]: `common` is its own play in 2023.1, tagged `common`, on every host of the
>   `common` group. A service tag no longer runs `common` at all, so fluentd, cron and kolla_toolbox changes need
>   `-t common` or an untagged run ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code),
>   [§4](#4-practical-consequences)).
> - **Handlers ignore tags:** this is why `-t keystone` can restart HAProxy [CODE]
>   ([§2.2](#22-handlers-ignore-tags-code)). In 2023.1 that restart is a stop/start, hosts without the VIP first.
> - **A tag never restricts which hosts a play targets; use `--limit` for that.** `--skip-tags haproxy` skips the entire
>   loadbalancer play ([§4](#4-practical-consequences)).

> **The single most important rule:** a tag name does **not** describe the work a run performs. What runs depends on:
>
> - which plays carry or inherit the tag;
> - the loadbalancer play's per-service includes;
> - handlers, which are **never filtered by tags**;
> - for MariaDB and RabbitMQ, the restart plays that the handlers fill through `group_by`;
> - ansible-core's loop-notify semantics.
>
> Everything below is read from the source; nothing was run against a host. The evidence labels **[CODE]** and
> **[NOT AVAILABLE]** are defined once, in [Evidence labels](../start/conventions.md#evidence-labels).

---

## 1. Where tags are defined

| Source | Example (evidence) | Inherited by |
|---|---|---|
| **Play-level tags** | loadbalancer play: `tags: [haproxy, keepalived, loadbalancer]` (`site.yml:105-108`); common play: `tags: [common]` (`site.yml:94-95`). All 10 plays of `nova.yml`, e.g. `tags: [nova, nova-cell, nova-cell-deploy, nova-cell-upgrade]` (`nova.yml:127-131`). Every play of `mariadb.yml` and `rabbitmq.yml` carries `mariadb` or `rabbitmq` (`mariadb.yml:8,21,35,47,59`; `rabbitmq.yml:8,33,48,65,89,105`) | every task of the play, including statically imported roles |
| **Role-level tags** in `roles:` | `- { role: neutron, tags: neutron }` (`site.yml:607-608`). memcached has `tags: [memcache, memcached]` (`:394-395`) | every task of the role. No role has a meta dependency in 2023.1 (no role has a `meta/` directory), so nothing else is pulled in |
| **Task-level tags on `include_role`** | loadbalancer block: `include_role: {name: nova, tasks_from: loadbalancer}` with `tags: [nova, nova-api]` (`site.yml:247-253`) | the include statement only; see [§2.3](#23-include_role--tags-always-inside-the-haproxy-play-code) |
| **`tags: always`** | gather-facts and group_by plays (`gather-facts.yml:22,54`, `site.yml:77`). `import_role: loadbalancer-config` in 43 of the 44 `loadbalancer.yml` files. nova-cell's `loadbalancer.yml` reaches it through `import_tasks: proxy_loadbalancer.yml` → looped `include_tasks: cell_proxy_loadbalancer.yml` → `import_role`, with `tags: always` at every level (`roles/nova-cell/tasks/loadbalancer.yml:55,91,127`; `proxy_loadbalancer.yml:19`; `cell_proxy_loadbalancer.yml:12`). `roles/opensearch/tasks/register.yml:7` (the congress role of Ussuri no longer exists) | runs regardless of `--tags`, unless the enclosing dynamic include is skipped |
| **Tags inside roles** | `nova/tasks/stop.yml:7` (`tags: nova`). `service-rabbitmq/tasks/main.yml:46-47` (`tags: [service-rabbitmq]`). `service-images-pull/tasks/main.yml:17-18`, `rabbitmq/tasks/precheck.yml:225,254` (`rabbitmq-ha-precheck`). `roles/common/tasks/main.yml:2` no longer carries `tags: common` | – |
| **Other playbooks** | `kolla-host.yml:10` (`baremetal`, role `openstack.kolla.baremetal`), `mariadb_backup.yml:6`, `mariadb_recovery.yml:6` (`mariadb`), `bifrost.yml:6` (`bifrost`) | – |

The full per-play tag list is generated in [Generated inventory
§1](../reference/generated-inventory.md#1-plays-executed-by-siteyml-in-order). Per-service cards (tags, task flow,
handlers, node types) are in [Components](../components/index.md). The output of `ansible-playbook --list-tags` against
the real `site.yml` is in [list-tags-site.txt](../reference/listings/list-tags-site.txt). Per play it shows the *task
tags* after inheritance. Whether that listing has been regenerated from 2023.1 is tracked in the reference lot; in
2023.1
`common` is a play tag of the common play only (`site.yml:86-97`).

---

## 2. Ansible 2.9 semantics that Kolla relies on

The heading keeps its Ussuri name for stable links. Kolla-Ansible 2023.1 accepts ansible-core 2.13 to 2.14
(`tools/kolla-ansible:10-11`); everything below is read in ansible-core 2.14.18. Whether ansible-core 2.13 behaves the
same is [NOT AVAILABLE] (not studied).

### 2.1 Dynamic `include_tasks` and tag inheritance [CODE]

Every role starts with `include_tasks: "{{ kolla_action }}.yml"` (dynamic). In ansible-core 2.14, tasks inside a
dynamically included file:

- **do inherit** the tags of the enclosing *role* and *play*: `nova`, `neutron`, `common`, `haproxy`, …;
- **do not inherit** tags written on the `include_tasks` statement itself (they apply to the include only, unless
  `apply:` is used — Kolla never uses `apply:`).

In the source (ansible-core 2.14.18): without `apply:`, the include itself becomes the parent of the included blocks
(`lib/ansible/playbook/task_include.py:131-150`, used at `lib/ansible/plugins/strategy/__init__.py:846-854`). An
include is not statically loaded (`task_include.py:50`), so `Block._get_parent_attribute` skips it and takes the tags
of the include's own parent, of the role and its dependency chain, and of the play
(`lib/ansible/playbook/block.py:297-368`; `tags` is an `extend` attribute, `lib/ansible/playbook/taggable.py:31`). The
included tasks are then filtered on those tags (`lib/ansible/plugins/strategy/linear.py:311`, `block.py:370-396`).
Applied to Kolla 2023.1, where `common` is a play of its own with `tags: [common]` (`site.yml:86-97`) and its role's
`include_tasks` carries no tag (`roles/common/tasks/main.yml:1-2`):

```text
--tags common            → the common play runs: the include_tasks and every task of the included file (play tag `common`)
--tags nova              → the common play is skipped (it carries only `common`); the nova plays' included tasks run
--tags service-rabbitmq  → nothing: the include that would load the tagged task does not carry the tag
```

The Ussuri behaviour (`-t common` a no-op, `common` dragged in by every service tag through meta dependencies) is gone:
no role in 2023.1 has a `meta/` directory, and `role: common` appears only in the common play (`site.yml:97`).

### 2.2 Handlers ignore tags [CODE]

A notified handler runs even if its own tags do not match `--tags`. Only the play's task blocks are filtered on tags
(ansible-core 2.14.18 `lib/ansible/executor/play_iterator.py:186-190`, `lib/ansible/playbook/block.py:370-396`); the
handler list is copied unfiltered (`play_iterator.py:197`) and a handler runs for every host it was notified for, with
no tag check (`play_iterator.py:430-453`; `lib/ansible/playbook/handler.py:56-57`). A notify also reaches every handler
that `listen`s to that name (`lib/ansible/plugins/strategy/__init__.py:633-648`). This is why `-t keystone` can restart
HAProxy: the `haproxy-config` task, imported under `tags: always` through `loadbalancer-config`
(`roles/loadbalancer-config/tasks/main.yml:2-4`), notifies `Restart haproxy container`
(`roles/haproxy-config/tasks/main.yml:22-23`). In 2023.1 that name is a `listen` topic of the loadbalancer role's
handlers, not a handler of its own (`roles/loadbalancer/handlers/main.yml:18-21, :66-68, :109-110, :191-193, :243-245`;
[fact sheet A §1.9][sheet-a-19]); the sequence is in [§5](#5-role--handler-map-core-services).

### 2.3 `include_role` + `tags: always` inside (the haproxy play) [CODE]

The loadbalancer play (the "haproxy play" of Ussuri) holds per-service `include_role` statements, which are dynamic
too. Their own tags (`keystone`, `nova`, …) only select the include statement: the included role's blocks get the
`include_role` as parent (ansible-core 2.14.18 `lib/ansible/playbook/role_include.py:109, :115-116`), which is skipped
as in [§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), while `tags: always` matches any `--tags`
(`lib/ansible/playbook/taggable.py:66-67`). For the work inside to run, 43 of the 44 `loadbalancer.yml` files wrap a
single `import_role: loadbalancer-config` with `tags: always` (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`), and
`loadbalancer-config` imports `haproxy-config` (when `haproxy_config_install`, true for every project except `mariadb`
with ProxySQL) and `proxysql-config` (when `enable_proxysql`, default `no`)
(`roles/loadbalancer-config/tasks/main.yml:2-8`,
`roles/loadbalancer-config/defaults/main.yml:2`, `group_vars/all.yml:742`). nova-cell's file reaches the same role
through `import_tasks: proxy_loadbalancer.yml`, a looped `include_tasks: cell_proxy_loadbalancer.yml` and then
`import_role` (`roles/nova-cell/tasks/cell_proxy_loadbalancer.yml:3-12`), with `tags: always` at every level, so the
effect is the same. Net effect: `-t <svc>` runs that service's HAProxy config on all `loadbalancer` hosts.

### 2.4 Loop notify: one changed item notifies the handlers of all items [CODE]

ansible-core 2.14.18 `lib/ansible/plugins/strategy/__init__.py:614-621`:

```python
for result_item in result_items:
    if '_ansible_notify' in result_item:
        if task_result.is_changed():          # <- aggregate status of the WHOLE loop
            for handler_name in result_item['_ansible_notify']:
                ... notify handler_name
```

`_ansible_notify` is attached to every executed (non-skipped) loop item (ansible-core 2.14.18
`lib/ansible/executor/task_executor.py:804-805`). The loop result is changed if any item changed
(`task_executor.py:124-128`, `lib/ansible/executor/task_result.py:96-106`). If *any* item changed, the templated
handler name of *every* executed item is notified. Kolla's `config.yml` and `check-containers.yml` loop over
`<role>_services` with `notify: "Restart {{ item.key }} container"`. So **a change that concerns one container
restarts every container of that role on that host.** Skipped items do not notify: an item whose `when` is false
returns before `_ansible_notify` is set (`task_executor.py:453-455`).

Applied to the real playbook [CODE]. An override that only touches `/etc/kolla/config/nova/nova-compute.conf` changes
only nova-compute's `nova.conf` (`roles/nova-cell/tasks/config.yml:69-88`; `defaults/main.yml:478-484`).
`kolla_set_configs --check` in `nova_compute` then exits 1 (kolla `docker/base/set_configs.py:36-39`, `:56-57`,
`:173-178`, `:240-242`, `:576-578`), so the `Check nova-cell containers` loop reports changed
(`module_utils/kolla_container_worker.py:59-66`, `module_utils/kolla_docker_worker.py:155-182`,
`library/kolla_docker.py:409`; `roles/nova-cell/tasks/check-containers.yml:2-22`). Its executed items on a compute host
with the defaults (`enable_nova_libvirt_container` true for the default `kvm`, `enable_nova_ssh: yes`,
`enable_nova_fake: no`; `group_vars/all.yml:731, :733, :771, :1031`) are `nova-libvirt`, `nova-ssh` and `nova-compute`
(`roles/nova-cell/defaults/main.yml:3-21, :53-64`), so the handlers restart `nova_compute`, **`nova_libvirt` and
`nova_ssh`** on every compute host.

A scheduler-only override changes the nova role's `Copying over nova.conf` loop, whose executed items on a `multinode`
controller are `nova-api` and `nova-scheduler` (`roles/nova/tasks/config.yml:64-82`; `nova-super-conductor` needs
`enable_cells`, default `no`, `group_vars/all.yml:646`, `roles/nova/defaults/main.yml:52`), so it restarts `nova_api`
*and* `nova_scheduler`.

Impact analysis in [Operations](../operations/index.md).

Kolla-Ansible 2023.1 accepts ansible-core 2.13 to 2.14 (`tools/kolla-ansible:10-11`). Only 2.14.18 was read; whether
2.13 has the same notify code is [NOT AVAILABLE].

### 2.5 `run_once` with `serial` [CODE]

With `kolla_serial` > 0, a `run_once` task runs once **per batch**, not once per play: each batch is a separate run of
the play (ansible-core 2.14.18 `lib/ansible/executor/playbook_executor.py:181-190`), and `run_once` only ends the host
loop inside that run (`lib/ansible/plugins/strategy/linear.py:217, :247-248`). This applies to bootstrap containers,
Keystone registration and DB creation. It is not harmful for idempotent steps, but it multiplies the number of DB-sync
containers and Keystone API calls ([fact sheet C, cross-cutting table][sheet-c-0]).

With `kolla_serial=1` and the three controllers of the `multinode` inventory (`inventory/multinode:3-7`,
`:117-118`, `:263-264`) [CODE]:

- `nova_api_bootstrap` (`run_once`, no `delegate_to`, `roles/nova/tasks/bootstrap_service.yml:2-21`) runs 3 times,
  once per controller batch, and each time on that batch's host (once more when `map_cell0` reports changed,
  `map_cell0.yml:66-67`).
- The `map_cell0` block (`run_once`, `roles/nova/tasks/map_cell0.yml:63`) runs 3 times; in 2023.1 it is delegated to
  the first `nova-api` host every time (`map_cell0.yml:64`).
- The compute registration wait plus `list_cells` run once per batch that holds a compute: they are gated on the batch's
  first compute and delegated to the first conductor (`roles/nova-cell/tasks/wait_discover_computes.yml:42-43, :88-90`;
  `discover_computes.yml:5, :21`; `roles/nova-cell/tasks/deploy.yml:19-37`).
- Nova containers restart strictly one host at a time, since each one-host batch finishes before the next starts.

The MariaDB and RabbitMQ restart plays do not use `kolla_serial`: they have their own `serial: "33%"`
(`mariadb.yml:20, :34`; `rabbitmq.yml:32, :88`), which is one host per batch for up to five hosts (a percentage rounds
down with a minimum of 1, `lib/ansible/utils/helpers.py:25-34`, used at `playbook_executor.py:295`).

### 2.6 `--list-tasks` is not usable for Kolla [CODE]

Because of [§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), `ansible-playbook site.yml --list-tasks -t nova`
lists only `include_tasks` placeholders for each role: the listing walks only the statically compiled play
(ansible-core 2.14.18 `lib/ansible/cli/playbook.py:202-207`), while dynamic includes are loaded at run time
(`lib/ansible/plugins/strategy/linear.py:291`). `config.yml` and `check-containers.yml` are invisible
([list-tasks-nova.txt](../reference/listings/list-tasks-nova.txt)). Plays whose host pattern depends on the
`group_by` groups (`&enable_nova_True`) also resolve to **0 hosts** at list time. Those groups are created at run time
(`[WARNING]: Could not match supplied host pattern, ignoring: enable_nova_True`, listing line 5), and an `&` pattern
keeps only the hosts that match it (`lib/ansible/inventory/manager.py:447-449`). The same holds for the MariaDB and
RabbitMQ restart plays, whose groups (`mariadb_restart`, `rabbitmq_restart`) only the handlers create. `--check` is no
substitute: `kolla_docker` does not declare check-mode support, so Ansible skips it under `--check` [CODE]
(`library/kolla_docker.py:345-349`; ansible-core 2.14.18 `lib/ansible/module_utils/basic.py:520-521`), and whether
such a run is usable is [NOT AVAILABLE] ([Predict and inspect a run](../operations/predict-a-run.md), [Open questions
Q9](../troubleshooting/open-questions.md#q9)). To predict restarts, use `genconfig` plus `kolla_set_configs --check`
(end of [§3.1](#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites)).

---

## 3. What a tag really executes (master table)

"Target hosts" assumes the 2023.1 `multinode` example inventory. "Containers" lists those that *can* be restarted or
recreated, **only if** a config, parameter or image change is detected: a restart handler runs only when a task that
notifies it reports *changed* ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) [CODE].
The notifying tasks are the config tasks and `check-containers`, whose `compare_container` reports *changed* only when
the container is missing, differs from the task in a compared parameter (image, volumes, environment, dimensions,
command, privileges, healthcheck, state, …), its systemd unit file is missing or differs, or `kolla_set_configs --check`
exits 1 or 137 or meets a Docker client error (`module_utils/kolla_container_worker.py:59-90, :320-327`;
`module_utils/kolla_docker_worker.py:155-193`; `module_utils/kolla_systemd_worker.py:149-162`) [CODE]. [NOT AVAILABLE]
Whether, on an unchanged cloud and apart from the exception below, every task that notifies a restart handler reports
*ok*, so that nothing restarts.

The kolla source shows one exception: `kolla_set_configs --check` exits 1 on every run for a `config_files` entry with
`preserve_properties` and no `perm`, as soon as a matching file or subdirectory has been copied (the expected `perm` is
then empty and never equals the actual mode; kolla `docker/base/set_configs.py:179-185, :205-210`; [Kolla images
§3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)). So
`prometheus_server` restarts on every deploy/reconfigure whenever `{{ node_custom_config }}/prometheus/extras/` holds
files already copied into the container (`roles/prometheus/templates/prometheus-server.json.j2:11-15`;
`roles/prometheus/tasks/deploy.yml:2-9`). A newly added extras file no longer makes the check fail as in Ussuri: in
2023.1 a source without a destination is a plain mismatch (`set_configs.py:166-169`), so `--check` exits 1 and
`prometheus_server` restarts ([Predict and inspect a run](../operations/predict-a-run.md)).

"common" means the `common` role (fluentd/cron/kolla_toolbox config, container check, `kolla_logs` volume). In 2023.1
it runs only in the common play (`site.yml:86-97`), on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` groups,
which are all children of `common` (`inventory/multinode:48-53, :239-249`). No other row runs it. A tag that selects a
loadbalancer include can also restart `haproxy` if that frontend changed ([§2.2](#22-handlers-ignore-tags-code)).

| Tag | Plays / roles selected | Tasks executed | Target hosts | Containers that can restart | Other side effects | Potential impact |
|---|---|---|---|---|---|---|
| *(no tag)* | all 79 plays | everything for `kolla_action` | all | all | all bootstrap/DB-sync containers, Keystone registration of all services | Full blast radius |
| `common` | the common play (`site.yml:86-97`) | config (`config.json`, `td-agent.conf`, cron logrotate, toolbox files), check-containers, `kolla_logs` volume, flush (`roles/common/tasks/deploy.yml`) [CODE] | every host of the `common` group (control, network, compute, storage, monitoring) | `fluentd`, `kolla_toolbox`, `cron` | – | Every host at once unless `ANSIBLE_SERIAL` is set; the containers are not on the VM or API path |
| `haproxy` (also `keepalived`, `loadbalancer`: same play) | loadbalancer play (`site.yml:99-342`): loadbalancer role (config-host, config, check-containers, no flush), all 44 loadbalancer includes evaluated, but only those of enabled services run (each except placement's has a `when` on `enable_*` flags, so the number depends on those flags), and the whole block only with `enable_haproxy` and `kolla_action` in deploy/reconfigure/upgrade/config (`site.yml:339-341`) | sysctl, keepalived kernel module, `haproxy.cfg`, `keepalived.conf`, keepalived checks, ProxySQL config when enabled, certs, the `services.d/*.cfg` of every enabled service (`roles/loadbalancer/tasks/config-host.yml`, `config.yml`) | `loadbalancer` hosts (network in `multinode`) | `haproxy`, `keepalived`, `proxysql` (if enabled) | – | API and DB path interruption if anything changed; hosts without the VIP first, then the VIP holder ([§5](#5-role--handler-map-core-services)); whether the VIP moves is [NOT AVAILABLE] ([A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour)) |
| `<svc>` (e.g. `keystone`, `glance`, `cinder`, `heat`, `placement`; `horizon` differs, see below the table) | loadbalancer play (that service's include only) + the service play | `services.d/<svc>*.cfg`; register, config, check-containers, bootstrap of the service | loadbalancer hosts + service hosts | haproxy (if its frontend changed), all of the service's containers on a host if any changed ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) | DB sync container, Keystone registration | Service API outage during the parallel restart; HAProxy restart if the frontend changed |
| `nova` | loadbalancer (nova + nova-cell includes), all 10 `nova.yml` plays | API/cell0/cell DB bootstrap, cell create/update, nova + nova-cell config/check, discovery, scheduler SIGHUP; reload/online-migration plays are no-ops except on `upgrade` | loadbalancer, `nova-api`, `nova-scheduler`, `nova-conductor`, consoles, **every `compute`** | nova API/scheduler/conductor/console proxies, **nova_compute, nova_libvirt, nova_ssh on all computes** | 6 one-shot container runs on `control01` when cell0 is mapped with an unchanged connection and the cell is unchanged (API DB sync, map_cell0, list_cells for cell0, cell DB sync, list_cells ×2) [CODE] (`roles/nova/tasks/bootstrap.yml:54-56`, `map_cell0.yml:2-64`, `roles/nova-cell/tasks/bootstrap.yml:41-43`, `create_cells.yml:2`, `discover_computes.yml:5`); RabbitMQ vhost/user for the cell; `kill -HUP` of nova_scheduler on every scheduler | See [Nova deep dive](../components/nova-deep-dive.md), [Reconfigure Nova](../operations/reconfigure-nova.md) |
| `nova-api` | loadbalancer nova include, API DB bootstrap play, nova play, scheduler cell-cache refresh, API reload/migrations | haproxy-config for the nova API/metadata frontends; nova_api + nova_cell0 DB/user creation, API DB sync and `map_cell0` on `nova-api[0]`; nova role: Keystone registration, config, check-containers, flush; scheduler SIGHUP | controllers + loadbalancer | nova_api, nova_scheduler, nova_super_conductor (only with `enable_cells`) | API DB sync, map_cell0 | Does **not** touch computes |
| `nova-cell` | loadbalancer nova-cell include, cell DB bootstrap, nova-cell play, cell reload/migrations | haproxy-config for the console-proxy frontends; on the first conductor: cell DB/user, RabbitMQ vhost/user (gated on the first conductor but run via `delegate_to` on the first host of the cell RPC/notify group, `rabbitmq[0]` by default), cell DB sync, cell create/update; nova-cell role: config-host (`br_netfilter`, sysctl, udev kvm rules, `qemu-kvm` masked), config, check-containers, flush, then compute discovery delegated to the first conductor | conductors, consoles, **all computes** | nova_conductor, consoles, nova_compute, nova_libvirt, nova_ssh | cell DB sync, cell create/update, RabbitMQ vhost/user for the cell, discovery | Touches every compute |
| `nova-bootstrap`, `nova-api-bootstrap`, `nova-cell-bootstrap` | the two bootstrap plays (`nova.yml:29-96`) | DB creation, DB sync containers, cell mapping | all `nova-api` hosts (API play) and all `nova-conductor` hosts (cell play); DB tasks and one-shot containers: `nova-api[0]`, `nova-conductor[0]` | none: `include_role` compiles only the role and its dependencies (ansible-core 2.14.18 `lib/ansible/playbook/role_include.py:114`, `lib/ansible/playbook/role/__init__.py:549-578`), and no role has dependencies in 2023.1; one-shot bootstrap containers only | RabbitMQ vhost/user for the cell | Schema changes only if images are newer |
| `nova-reload`, `nova-api-reload`, `nova-cell-reload` | reload plays (`nova.yml:164-225`) | `recreate_or_restart` of nova services **only when `kolla_action == upgrade`** | as named | on upgrade: all nova services | – | No-op outside upgrade |
| `nova-online-data-migrations` (+ `-api-`, `-cell-`) | `nova.yml:230-272` | `nova-manage db online_data_migrations` | `nova-api[0]`, `nova-conductor[0]` | – | upgrade only | – |
| `nova-refresh-scheduler-cell-cache` | `nova.yml:140-156` (`import_role: nova, tasks_from: refresh_scheduler_cell_cache`) | `kill -HUP` of `nova_scheduler` (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:4-12`) | nova-scheduler hosts | `nova_scheduler` only gets SIGHUP (no restart) | – | Runs on **every** deploy/reconfigure with `nova` or `nova-api` (`nova.yml:154-156`); it adds only the signal |
| `neutron` | loadbalancer neutron include, neutron play (hosts include **`compute`** and `manila-share`, `site.yml:590-608`) | plugin/agent check, register, config-host (modules, sysctl), config, check-containers, DB and DB-user creation, `bootstrap_neutron` DB-sync container on every deploy and reconfigure (`roles/neutron/tasks/deploy.yml:2-23`, `bootstrap.yml:38`, `bootstrap_service.yml:2-21`, no `when`) | loadbalancer, neutron-server, network agent hosts, **every compute** | neutron_server, all agents on a host if any changed ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) | DB sync container | OVS agent restarts on computes, L3/DHCP agent restarts on network nodes; [NOT AVAILABLE] whether flows are resynced and traffic is interrupted ([Reconfigure Neutron](../operations/reconfigure-neutron.md)) |
| `openvswitch` | openvswitch play, only while `enable_ovs_dpdk` is `no` (`site.yml:546-555`; `ovs-dpdk` has its own play and tag) | config-host, config, check-containers, flush, **post-config**: `system-id` and `hw-offload` set through `openvswitch_db`, bridge ensure (`roles/openvswitch/tasks/deploy.yml`, `post-config.yml:3-34`) | `openvswitch` group (network + **compute** + manila-share) | `openvswitch_db`, `openvswitch_vswitchd` | a changed `system-id`/`hw-offload` notifies `Restart openvswitch-vswitchd container`, run at the end of the play (`post-config.yml:21-22`) | [NOT AVAILABLE] whether a vswitchd restart interrupts **all VM traffic** on that host ([Risk register R7](risk-register.md#r7)) |
| `ovn` (also `ovn-controller`, `ovn-db`: one play each) | ovn-controller play and ovn-db play (`site.yml:568-588`) | ovn-controller: config, check-containers, chassis setup (`br-int`, then 9 `external_ids` keys through `openvswitch_db`, `roles/ovn-controller/tasks/setup-ovs.yml:2-39`), flush; ovn-db: cluster lookup, config, check-containers, flush, DB bootstrap | ovn-controller (**every compute and network**), OVN DB hosts (control) | `ovn_controller`; `ovn_nb_db`, `ovn_sb_db`, `ovn_northd` | sets or removes `ovn-cms-options` from `ovn_cms_opts` (`setup-ovs.yml:39`) | [A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable) |
| `mariadb` | loadbalancer mariadb include, the five `mariadb.yml` plays (`mariadb.yml:3-72`) | cluster lookup, bootstrap or recovery when needed, config, check-containers; the handlers only sort hosts into `mariadb_restart` / `mariadb_start` (`roles/mariadb/handlers/main.yml:56-73`), and the restart plays then restart them in `serial: "33%"` batches, each waiting for the port and WSREP `Synced` (`roles/mariadb/tasks/restart_services.yml`); post-config: register, check | mariadb hosts | mariadb (one host per batch with three nodes), mariadb_clustercheck | – | [B §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb) |
| `rabbitmq` | loadbalancer include, **all six** `rabbitmq.yml` plays (`rabbitmq` and `outward-rabbitmq` share the tag) | haproxy-config for the `rabbitmq_management` frontend; version check, removal of the `ha-all` policy while `om_enable_rabbitmq_high_availability` is `false` (default), config (`config.json`, `rabbitmq-env.conf`, `rabbitmq.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`, `enabled_plugins`), check-containers, volume creation and, only for a new volume, the `rabbitmq_bootstrap` container; the handler only adds the host to `rabbitmq_restart` (`roles/rabbitmq/handlers/main.yml:2-6`); restart play: drain, restart, `rabbitmqctl wait`, `serial: "33%"`; post-config: feature flags | rabbitmq hosts | rabbitmq (one by one with three nodes) | – | [B §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice) |
| `memcached` / `memcache` | memcached play (`memcache` does **not** select the loadbalancer include) | config dir + `config.json`, check-containers. No flush: the restart handler runs at the end of the play. `memcached` also selects the loadbalancer include, which renders a frontend only with `enable_haproxy_memcached` (default `no`, `group_vars/all.yml:637`) | memcached hosts | memcached (all at once) | – | [NOT AVAILABLE] whether the restart empties the token cache and the Horizon sessions kept there ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) |
| `chrony` | **none** in 2023.1: `site.yml` has no chrony play and there is no chrony role (`ansible/roles/`) | only the `always` plays (fact gathering, `group_by`) | – | none | – | No longer a way to reach every host; use `-t common` ([§4](#4-practical-consequences)) |
| `iscsi` | iscsi play (`site.yml:417-426`), only where `enable_iscsid` is true (default: `enable_cinder` and `enable_cinder_backend_iscsi`, `group_vars/all.yml:700`) | config-host (load and persist `configfs`), config dirs + `config.json`, check-containers, flush | iscsid (compute + storage + ironic), tgtd (storage) | iscsid, tgtd | – | Volume attach path on computes ([D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)) |
| `service-rabbitmq` | the RabbitMQ user/vhost blocks inside roles | **nothing** on its own (inside dynamic includes) | – | – | – | Not usable as a selector |
| `baremetal` | `kolla-host.yml` only (role `openstack.kolla.baremetal` from ansible-collection-kolla, `kolla-host.yml:4-10`) | host preparation: `/etc/hosts`, packages, Docker, `kolla` user, Docker SDK, AppArmor for libvirt (ansible-collection-kolla `roles/baremetal/tasks/main.yml`, `install.yml:34-38`, `post-install.yml`) | `baremetal` group (all node groups in `multinode`) | **Docker daemon restart if `daemon.json` changed** (ansible-collection-kolla `roles/docker/tasks/config.yml:42-47`, `handlers/main.yml:10-15`) | packages, users, `/etc/hosts` | [E §1–3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#1-ansiblekolla-hostyml-the-bootstrap-servers-command) |

`horizon` follows the `<svc>` row without registration and, by default, without bootstrap. The role has no
`register.yml`, so it is never registered in Keystone. Its DB creation and `bootstrap_horizon` DB sync run only when
`horizon_backend_database` is true (default `{{ enable_murano | bool }}`, `group_vars/all.yml:1052`;
`roles/horizon/tasks/deploy.yml:10-11`). With defaults, `-t horizon` runs the loadbalancer horizon include, config,
check-containers and, if anything changed, the horizon restart handler.

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
| `haproxy` | `haproxy.cfg`, `services.d/*.cfg` of enabled services, `keepalived.conf`, keepalived checks, ProxySQL config when enabled, TLS PEMs, sysctl | no direct effect; [NOT AVAILABLE] whether instance metadata requests, which the metadata agents send to nova through the internal FQDN (`roles/neutron/templates/metadata_agent.ini.j2:4`), fail while HAProxy is down | **yes**: HAProxy is stopped and started (never reloaded); hosts that do not hold the VIP go first and are waited for on the monitor port, then the VIP holder's HAProxy is stopped and started (`roles/loadbalancer/handlers/main.yml:54-68, :90-118, :179-193, :224-253`), and all APIs and the DB path go through it; [NOT AVAILABLE] whether established connections are cut and whether keepalived drops or moves the VIP while the master's HAProxy is down ([R8](risk-register.md#r8)) | control plane only | yes if nothing reports a change, since the restart handlers then never run [CODE] ([§2.4](#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)); with a change, prefer a window | facts of every backend host; certificates if TLS is on |
| `<svc>` API service (`keystone`, `glance`, `cinder`, `heat`, `placement`, `horizon`) | service configs on its hosts, its `services.d` frontend | none for keystone/heat/placement/horizon; glance/cinder transfers in progress are SIGKILLed after 60 s (`docker_graceful_timeout`, [R24](risk-register.md#r24)) | **yes**: the service restarts on all its hosts at once; [NOT AVAILABLE] whether other APIs fail authentication while Keystone restarts ([R19](risk-register.md#r19)) and whether scheduling stops while Placement restarts ([Nova deep dive §3](../components/nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate) item 4) | cinder: volume operations; `iscsid` and `tgtd` are in the `iscsi` play, not under `-t cinder` (`site.yml:417-426`) | yes, it is the intended unit; it still runs Keystone registration and DB sync (horizon: neither, by default); batch with `ANSIBLE_SERIAL`; the glance file backend has one host ([R20](risk-register.md#r20)) | MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP |
| `nova` | API and cell `nova.conf`, `config.json`, policy, libvirt (`libvirtd.conf`, `qemu.conf`, SASL), nova-ssh files, Ceph keyrings when enabled, nova frontends | [CODE] `nova_libvirt` restarts with any nova-cell drift on a compute (loop-notify, [R1](risk-register.md#r1)); [NOT AVAILABLE] whether live migrations in progress fail and whether running VMs survive ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), [Reconfigure Nova §5](../operations/reconfigure-nova.md#5-running-vms-live-migration-scheduling)) | nova API, scheduler and conductors restart at once; [NOT AVAILABLE] whether instance actions fail meanwhile | [NOT AVAILABLE] whether attach/detach and port binding in flight fail; no OVS change | only with batching and a window; prefer `genconfig` + `deploy-containers --limit` ([Write config first, apply in controlled batches §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)) | MariaDB, RabbitMQ, memcached, Keystone, Placement, Glance, Neutron registered |
| `nova-api` | API-side `nova.conf`, `config.json`, policy, nova frontends | none | nova API, scheduler, super-conductor (with `enable_cells`) | none | yes; does not touch computes | as `nova` |
| `nova-cell` | cell `nova.conf`, libvirt, nova-ssh and Ceph files on computes and conductors, console frontends | **yes**, as `nova` | conductors and console proxies | as `nova` | as `nova` | the API DB and cell0 mapping (`nova-api`/`nova`), RabbitMQ |
| `neutron` | `neutron.conf`, `ml2_conf.ini`, `openvswitch_agent.ini`, `l3_agent.ini`, `dhcp_agent.ini`, `metadata_agent.ini` (+ enabled features), neutron frontend | **yes**: OVS agent restart on every compute ([NOT AVAILABLE] whether and how it resyncs flows, and whether traffic is lost), L3/DHCP/metadata agent restarts on network nodes; running L3 agents restart in the order of the host list, spaced by `neutron_l3_agent_failover_delay` per host (default `0`, so no spacing; `roles/neutron/handlers/main.yml:136-157`, `defaults/main.yml:633`); with `enable_neutron_agent_ha`, the L3 agent wrapper runs `neutron-netns-cleanup` before the agent starts, and what that command deletes is [NOT AVAILABLE] ([R6](risk-register.md#r6)) | neutron-server restarts on all controllers at once | **networking: yes** ([Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking)); storage: no | risky without batching ([R5](risk-register.md#r5), [R6](risk-register.md#r6)) | Open vSwitch or OVN running, MariaDB, RabbitMQ, Keystone |
| `openvswitch` | `config.json` of `openvswitch_db`/`openvswitch_vswitchd`, `start-ovs`, `start-ovsdb-server`; `system-id` and `hw-offload` (through `openvswitch_db`), and bridges on network nodes (and on computes when `computes_need_external_bridge`) | [NOT AVAILABLE] whether running VMs are affected if `openvswitch_vswitchd` restarts or is recreated, e.g. whether all VM traffic on the host stops until flows are reinstalled ([R7](risk-register.md#r7)). The kernel module stays loaded and `conf.db` keeps bridges and ports, but nothing saves or restores flows ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 13) | none | **networking: yes** | yes if unchanged; a changed `system-id` or `hw-offload` now restarts `openvswitch_vswitchd` (`post-config.yml:21-22`); whether the `openvswitch_db` module reports *ok* when the value is already set is [NOT AVAILABLE] (the module is not in the studied sources); image changes per host batch | `openvswitch` kernel module |
| `ovn` | `config.json` of the OVN containers; chassis `external_ids` (`ovn-cms-options` set from `ovn_cms_opts` or removed) | [NOT AVAILABLE] whether an ovn-controller restart re-programs flows on the host | NB/SB DB restarts interrupt neutron-server's OVN driver | **networking: yes** | check manual `ovn-cms-options` first ([A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable)) | Open vSwitch |
| `mariadb` | `galera.cnf` (lists all nodes), `config.json`, clustercheck files, `wsrep-notify.sh` | none directly | restart in `serial: "33%"` batches of the hosts the handlers put in `mariadb_restart` (one host at a time with three nodes, `mariadb.yml:14-26`); HAProxy's single active backend is the first shard host, the others are `backup` (`roles/mariadb/defaults/main.yml:64`); [NOT AVAILABLE] in which batch it restarts ([R9](risk-register.md#r9)) | DB only | only on a healthy, fully synced cluster | every node `Synced` |
| `rabbitmq` | `rabbitmq.conf`, `rabbitmq-env.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`, `enabled_plugins`, `config.json` | none directly; [NOT AVAILABLE] whether nova-compute and the agents lose RPC while their broker restarts | restarts are one by one with three nodes: each node is drained into maintenance mode, restarted and waited for (`rabbitmq.yml:26-41`; `roles/rabbitmq/tasks/restart_services.yml:9-39`); [NOT AVAILABLE] whether RPC-backed API calls time out meanwhile | none directly; [NOT AVAILABLE] whether the agents reconnect by themselves | yes on a healthy cluster; membership changes are [R3](risk-register.md#r3) | no partitions, all nodes running |
| `memcached` / `memcache` | `config.json` | none | memcached restarts on all memcached hosts at once; [NOT AVAILABLE] whether that empties the token cache (with extra load on Keystone) and loses the Horizon sessions kept in memcached ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) | none | yes, off-peak | none |
| `chrony` | none: no chrony play in 2023.1 | none | none | none | does nothing | – |
| `common` | `config.json`, `td-agent.conf`, cron logrotate config (lists services by their `enable_*` flags), kolla_toolbox files, on **every** host of `common` [CODE] (`roles/common/tasks/config.yml`) | none | none (common containers only) | none | yes; the way to push common config fleet-wide ([§4](#4-practical-consequences)) | – |
| `iscsi` | `config.json` of `iscsid`/`tgtd`; `configfs` persistence | `iscsid`: [NOT AVAILABLE] whether existing sessions are kernel-held and whether attach/detach during the window fails. `tgtd` (LVM backend with `tgtadm`, the default target helper on Debian/Ubuntu) has no start script and empty `config_files`, and its command is a bare `tgtd`: nothing in its start path runs `tgt-admin` to load `/etc/tgt/targets.conf` (where the image adds `include /var/lib/cinder/volumes/*`). [NOT AVAILABLE] whether tgtd loads that file itself or keeps targets only in memory, and so whether a `tgtd` restart cuts disk I/O for VMs using LVM volumes from that host until the targets are re-created ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)) | none | **storage path on computes** ([D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)) | with care, per host batch | – |
| `baremetal` (`bootstrap-servers`) | `daemon.json`, `/etc/hosts`, packages, users | **yes** if `daemon.json` changes: the Docker restart (`state: restarted` unless `docker_systemd_reload`, default `false`, ansible-collection-kolla `roles/docker/handlers/main.yml:10-15`, `defaults/main.yml:63`) stops every container, `nova_libvirt` and OVS included ([R14](risk-register.md#r14)) | yes on controllers | yes | no on a live host unless `daemon.json` is unchanged; use `--limit` | – |

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

1. **Reconfiguring `common` is `-t common` in 2023.1.** `common` is its own play (`site.yml:86-97`) and no service
   play runs it [CODE] ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code)). Changes to fluentd, cron or
   kolla_toolbox config reach a host only through:
   - `-t common`, on every host of the `common` group;
   - an untagged run.

   `-t chrony` no longer exists (no chrony play), and `-t nova` or `-t neutron` no longer touch the common containers.
2. **A service tag drags in shared infrastructure.**
   - `-t nova` also runs the loadbalancer play (nova frontends), Keystone registration and the DB bootstrap containers
     [CODE] (`site.yml:247-260`, `nova.yml:99-135`, `roles/nova/tasks/deploy.yml:2`, `nova.yml:29-96`). It no longer
     runs `common`: the Ussuri `meta/main.yml` dependency of nova and nova-cell does not exist in 2023.1.
   - `-t neutron` also runs the neutron role on all computes.
   - A tag never restricts *which hosts* a play targets; use `--limit` for that.
3. **Handlers make the impact data-dependent.** The same command can be a no-op or a fleet-wide restart, depending
   on whether a rendered file changed. That in turn depends on *global* variables (`enable_*`, group membership,
   passwords), not only on the tagged service [CODE]: e.g. common's cron logrotate config lists services by their
   `enable_*` flags and notifies `Restart cron container` (`roles/common/tasks/config.yml:138-209`). Since only the
   common play renders it, enabling a service with `-t <svc>` leaves the logrotate config stale until `-t common` or an
   untagged run.
4. **`--skip-tags` can avoid the loadbalancer play.** `--skip-tags haproxy` skips the entire loadbalancer play,
   including the per-service includes ([fact sheet A §1.9][sheet-a-19]), because every task of the play inherits the
   play tags `haproxy`, `keepalived` and `loadbalancer` and one skipped tag is enough
   (ansible-core 2.14.18 `lib/ansible/playbook/taggable.py:78-86`), while leaving the service play untouched. Combining
   `-t nova` with `--skip-tags haproxy` is valid. Most service tags (`keystone`, `glance`, `neutron`, `nova`, …) select
   both the service's loadbalancer include and the service play(s), so for a single-tag service such as keystone this is
   the tag-based way to drop the HAProxy part. Some tags select no loadbalancer include at all:
   - `memcache` (only the memcached play);
   - nova's narrower play tags: `-t nova-bootstrap,nova-api-deploy,nova-cell-deploy,nova-refresh-scheduler-cell-cache`
     does what a `-t nova` deploy/reconfigure does, minus the loadbalancer includes (`site.yml:247-260`);
   - `common`, `openvswitch`, `ovn`, `iscsi` (their own plays only).
5. **Tags do not change `kolla_action` logic.** For a given tag, `deploy` and `reconfigure` execute the same tasks (e.g.
   `-t nova deploy` and `-t nova reconfigure`; [Repository architecture
   §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). Apart from swift and bifrost, whose
   `reconfigure.yml` has its own logic, every role's `reconfigure.yml` imports or includes `deploy.yml` [CODE]. The
   Ussuri exception of Neutron's `bootstrap_neutron` container is gone: it runs on deploy and reconfigure alike
   (`roles/neutron/tasks/bootstrap_service.yml:2-21`, no `when`; `reconfigure.yml:2`). The other difference is the
   `kolla_serial` pass-through
   ([Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook)).

---

## 5. Role → handler map (core services)

Handlers run in **definition order** after `meta: flush_handlers` (end of `deploy.yml`) or at the end of the play. All
use `kolla_docker` `recreate_or_restart_container` unless noted. The complete list for all roles is in [Generated
inventory §3](../reference/generated-inventory.md#3-role-task-structure-handlers-and-helper-role-usage).

| Role | Handlers (definition order) | Special logic | Evidence |
|---|---|---|---|
| common | Restart fluentd → Restart kolla-toolbox (→ Initializing toolbox: `docker exec … ansible --version`) → Restart cron | – | `roles/common/handlers/main.yml` |
| haproxy (role `loadbalancer` in 2023.1) | Check IP addresses on the API interface → Group HA nodes by status (VIP holder or not) → Stop backup keepalived / haproxy / proxysql → Start backup haproxy (→ wait on monitor port) → Start backup proxysql (→ wait) → Start backup keepalived → Stop master haproxy / proxysql / keepalived → Start master haproxy (→ wait) → Start master proxysql (→ wait) → Start master keepalived → Wait for haproxy / proxysql to listen on the VIP | all are `listen` handlers on `Restart haproxy container`, `Restart proxysql container` or `Restart keepalived container`; keepalived is stopped only when it is itself notified; stop/start, never reload; no flush in `deploy.yml` | `roles/loadbalancer/handlers/main.yml:1-329`, `roles/loadbalancer/tasks/deploy.yml`, [A §1.5](../reference/factsheets/a-infra-lb-ovn.md#15-handlers-ansibleroleshaproxyhandlersmainyml-definition-order--run-order-see-common-mechanics) |
| mariadb | Bootstrap MariaDB cluster (listen: first container, port, WSREP, then `mariadb_bootstrap_restart` group) → Restart MariaDB on existing cluster members (`group_by: mariadb_restart`) → Start MariaDB on new nodes (`group_by: mariadb_start`) → Restart mariadb-clustercheck | the restart itself is in the `mariadb.yml` restart plays, `serial: "33%"`, waiting for port + WSREP `Synced` | `roles/mariadb/handlers/main.yml:2-91`, `mariadb.yml:14-52`, `roles/mariadb/tasks/restart_services.yml`, [B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order) |
| rabbitmq | Restart rabbitmq container (`group_by: <project>_restart`) | the restart play drains the node (`rabbitmq_upgrade drain`), restarts it and waits with `rabbitmqctl wait`, `serial: "33%"` | `roles/rabbitmq/handlers/main.yml:2-6`, `rabbitmq.yml:26-41`, `roles/rabbitmq/tasks/restart_services.yml:9-39`, [B §2.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#25-handlers-ansiblerolesrabbitmqhandlersmainyml-in-definition-order) |
| keystone | (Init keystone database upgrade, upgrade only) → Restart keystone-ssh → Restart keystone-fernet → Restart keystone → (Finish keystone database upgrade, upgrade only) | all hosts at once | `roles/keystone/handlers/main.yml:5-98`, [B §3.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#35-handlers-ansibleroleskeystonehandlersmainyml-order-is-load-bearing-comment-2-3) |
| nova | Restart nova-super-conductor → nova-scheduler → nova-api | skipped on upgrade when `nova_safety_upgrade` | `roles/nova/handlers/main.yml` |
| nova-cell | Restart nova-conductor → novncproxy → spicehtml5proxy → serialproxy → nova-ssh → **nova-libvirt** (retries 5; with `libvirt_enable_sasl`, default `true`, notifies the two next) → Checking libvirt container is ready → Create libvirt SASL user → Reload libvirtd (host service, notified from `external_ceph.yml`) → nova-compute → nova-compute-ironic → fake → Wait for nova-compute services (upgrade only, `nova_compute_startup_delay` pause) | libvirt is restarted **before** nova-compute | `roles/nova-cell/handlers/main.yml:1-225`, `defaults/main.yml:562` |
| neutron | one handler per agent/server; L3 agent: stopped agents started first, then running agents in host-list order, each loop item preceded by a `neutron_l3_agent_failover_delay` pause (default `0`: no spacing) | L3 agent only | `roles/neutron/handlers/main.yml`, `:90-157` |
| openvswitch | Restart openvswitch-db-server (→ Waiting for openvswitch_db) → Restart openvswitch-vswitchd | – | `roles/openvswitch/handlers/main.yml:1-44` |

## Related

- [Operations](../operations/index.md) (impact of each scenario, commands)
- [Risk register](risk-register.md) (risks [R1–R25](risk-register.md#r1))
- [Components](../components/index.md)
- [Tag index](tag-index.md) (tag index)

[sheet-a-19]: ../reference/factsheets/a-infra-lb-ovn.md#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy
[sheet-c-0]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#0-cross-cutting-facts-apply-to-all-five-roles
