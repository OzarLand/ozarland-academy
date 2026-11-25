---
title: What a tag really executes
description: "How tags select work in Kolla-Ansible 2025.1 and what each important tag executes: target hosts, containers that can restart, per-tag answers."
tags: [tags, handlers, loop-notify, serial, limit, nova, neutron, openvswitch, ovn, haproxy, loadbalancer, letsencrypt, etcd, keystone, iscsi, valkey, reconfigure]
remember:
  - "Handlers are still never filtered by tags, but in 2025.1 a service tag no longer restarts HAProxy: the step that compares the HAProxy container carries only the <code>haproxy</code>, <code>keepalived</code> and <code>loadbalancer</code> tags, so <code>-t keystone</code> rewrites the Keystone frontend file and leaves HAProxy on the old configuration. <span class=\"ev ev-code\">CODE</span>"
  - "Loop-notify is gone: a nova-compute-only override restarts <code>nova_compute</code> only, but still on every compute host the play reaches. <span class=\"ev ev-code\">CODE</span>"
  - "A tag never restricts which hosts a play targets; use <code>--limit</code> for that."
  - "<code>-t common</code> is the only tag that runs <code>common</code>: fluentd, cron and kolla_toolbox changes need <code>-t common</code> or an untagged run. In 2025.1 that run no longer pulls the fluentd image. <span class=\"ev ev-code\">CODE</span>"
  - "<code>--list-tasks</code> is not usable for Kolla; to predict restarts, use <code>genconfig</code> plus <code>kolla_set_configs --check</code>. <span class=\"ev ev-code\">CODE</span>"
scenarios:
  - title: "Try a nova-compute change on a few computes first"
    situation: "Your cloud has 40 computes. You changed an override in <code>/etc/kolla/config/nova/nova-compute.conf</code> and want it applied to 4 computes only, as a first step. A colleague says: \"Just run <code>reconfigure -t nova-cell</code>: the tag only picks the hosts that need it.\""
    ask: "What would you do?"
    choices:
      - text: "Run <code>kolla-ansible reconfigure -t nova-cell</code> as suggested, without <code>--limit</code>."
        verdict: "avoid"
        why: "A tag never restricts which hosts a play targets; use <code>--limit</code> for that. <code>nova-cell</code> touches every compute, and the override restarts <code>nova_compute</code> on every compute host at once (<code>reconfigure</code> always runs with <code>kolla_serial=0</code>) <span class=\"ev ev-code\">CODE</span>."
      - text: "Run <code>kolla-ansible reconfigure -t nova --limit</code> on the 4 computes, straight away."
        verdict: "risky"
        why: "<code>--limit</code> does restrict the hosts, and in 2025.1 only <code>nova_compute</code> restarts there, since loop-notify is gone <span class=\"ev ev-code\">CODE</span>. But the run also takes the Nova API, scheduler and conductor hosts out of the limit, and whether live migrations in progress fail is <span class=\"ev ev-na\">NOT AVAILABLE</span>. The page says: only with batching and a window; prefer <code>genconfig</code> + <code>deploy-containers --limit</code>."
      - text: "Run <code>genconfig</code>, predict the restarts with <code>kolla_set_configs --check</code>, then apply with <code>deploy-containers --limit</code> on the 4 computes, in a window."
        verdict: "best"
        why: "To predict restarts, use <code>genconfig</code> plus <code>kolla_set_configs --check</code>: <code>--list-tasks</code> cannot show the tasks inside roles, and <code>--check</code> is no substitute <span class=\"ev ev-code\">CODE</span>. <code>deploy-containers</code> then restarts only the containers reported changed, on the hosts of the limit."
    see: "31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites"
  - title: "Push a common config change to every host"
    situation: "You need to push a change of the common config (fluentd, cron logrotate, kolla_toolbox) to every host of the cloud. A colleague suggests <code>-t chrony</code>, because that tag reached every host in old releases."
    ask: "What would you do?"
    choices:
      - text: "Run <code>kolla-ansible deploy -t common</code>, with <code>-e kolla_serial=N</code> if you want batches."
        verdict: "best"
        why: "<code>common</code> is its own play and no service play runs it <span class=\"ev ev-code\">CODE</span>. For this role <code>deploy</code> and <code>reconfigure</code> run the same tasks, and <code>deploy</code> is the one that accepts <code>-e kolla_serial=N</code>: <code>reconfigure</code> always adds <code>kolla_serial=0</code> after your <code>-e</code> <span class=\"ev ev-code\">CODE</span>. The common containers are not on the VM or API path."
      - text: "Run <code>kolla-ansible reconfigure -t chrony</code>, as your colleague suggests."
        verdict: "avoid"
        why: "<code>chrony</code> does not exist in 2025.1: there is no chrony play and no chrony role, so the tag runs only the <code>always</code> plays (fact gathering, <code>group_by</code>). It is not a way to reach every host; use <code>-t common</code>."
      - text: "Run an untagged <code>reconfigure</code> of the whole cloud."
        verdict: "risky"
        why: "An untagged run also reaches the common config, but it runs all 71 plays on all hosts, every host at once: every changed container restarts, with all bootstrap/DB-sync containers and the Keystone registration of all services. The page calls it the full blast radius."
    see: "4-practical-consequences"
quiz:
  - q: "In 2025.1, does <code>kolla-ansible reconfigure -t keystone</code> restart HAProxy when the Keystone frontend changed?"
    options: ["Yes, because handlers ignore tags", "No: the step that would notify the HAProxy restart carries only the loadbalancer play's tags, so it is skipped"]
    answer: 1
    explain: "The final <code>check-containers</code> include of the loadbalancer play has no tag of its own and inherits only <code>haproxy</code>, <code>keepalived</code> and <code>loadbalancer</code> <span class=\"ev ev-code\">CODE</span>. Handlers still ignore tags, but nothing notifies the HAProxy handler in that run."
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
  - q: "With <code>kolla-ansible deploy -e kolla_serial=1</code>, is the etcd play run one host at a time?"
    options: ["Yes, like every service play", "No: the etcd play has no <code>serial</code>"]
    answer: 1
    explain: "The etcd play does not set <code>serial</code>, so <code>kolla_serial</code> does not batch it; its handlers order the restarts instead <span class=\"ev ev-code\">CODE</span>."
    see: "25-run_once-with-serial-code"
---

# What a tag really executes

How tags actually select work in Kolla-Ansible 2025.1, and what each important tag executes. Read [Repository
architecture §3–4](../concepts/repository-architecture.md#3-anatomy-of-siteyml) first for the play and role skeleton.

> [!NOTE]
> **Key answers**
>
> - **What a tag executes, on which hosts, and which containers can restart:** the master table
>   ([§3](#3-what-a-tag-really-executes-master-table)). Config files, running VMs, API availability, networking and
>   storage, safety and prerequisites per tag:
>   [§3.1](#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites).
> - **Which tags reach the computes:** among the tags of this page, `nova`, `nova-cell`, `neutron`, `openvswitch`,
>   `ovn` (through `ovn-controller`), `iscsi` (when `iscsid` is enabled) and `common` target compute hosts, as do
>   `baremetal` (`bootstrap-servers`, all hosts) and `nova-reload`/`nova-cell-reload` (work only on `upgrade`);
>   `nova-api` does not touch computes ([§3](#3-what-a-tag-really-executes-master-table)). `chrony` still does not
>   exist.
> - **Changed in 2025.1: loop-notify is gone.** The shared check step notifies only the containers reported changed,
>   so a nova-compute-only override restarts `nova_compute` and no longer `nova_libvirt` and `nova_ssh` [CODE]
>   ([§2.4](#24-loop-notify-is-gone-in-20251-code)).
> - **Changed in 2025.1: a service tag no longer restarts HAProxy.** Handlers still ignore tags, but the only step that
>   notifies the HAProxy restart is skipped under `-t <svc>`; the new frontend file waits for a later run with no tag
>   or with `-t haproxy` [CODE] ([§2.2](#22-handlers-ignore-tags-code)).
> - **`-t common` does the work** [CODE]: `common` is its own play, tagged `common`, on every host of the `common`
>   group. A service tag does not run `common`, so fluentd, cron and kolla_toolbox changes need `-t common` or an
>   untagged run ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), [§4](#4-practical-consequences)).
>   Changed in 2025.1: it no longer pulls the fluentd image.
> - **A tag never restricts which hosts a play targets; use `--limit` for that.** `--skip-tags haproxy` skips the entire
>   loadbalancer play ([§4](#4-practical-consequences)).
> - **New and removed tags:** `valkey` is new (a play of its own, `site.yml:399-411`); the `swift` tag selects no play
>   any more, and `nova-libvirt-version-check` and `nova-libvirt-script-check` are new tags inside the nova-cell role
>   ([§1](#1-where-tags-are-defined), [Tag index](tag-index.md)).

> **The single most important rule:** a tag name does **not** describe the work a run performs. What runs depends on:
>
> - which plays carry or inherit the tag;
> - the loadbalancer play's per-service includes, and its final check step, which carries only the play's tags;
> - handlers, which are **never filtered by tags**;
> - for MariaDB and RabbitMQ, the restart plays that the handlers fill through `group_by`.
>
> Everything below is read from the source; nothing was run against a host. The evidence labels **[CODE]** and
> **[NOT AVAILABLE]** are defined once, in [Evidence labels](../start/conventions.md#evidence-labels).

---

## 1. Where tags are defined

| Source | Example (evidence) | Inherited by |
|---|---|---|
| **Play-level tags** | loadbalancer play: `tags: [haproxy, keepalived, loadbalancer]` (`site.yml:115-118`); common play: `tags: [common]` (`site.yml:100-101`). All 10 plays of `nova.yml`, e.g. `tags: [nova, nova-cell, nova-cell-deploy, nova-cell-upgrade]` (`nova.yml:135-139`). Every play of `mariadb.yml` and `rabbitmq.yml` carries `mariadb` or `rabbitmq` (`mariadb.yml:12-13, :29-30, :47-48, :63-64, :79-80`; `rabbitmq.yml:12-13, :41-42, :60-61`) | every task of the play, including statically imported roles and the loadbalancer play's final `check-containers` include (`site.yml:319-324`) |
| **Role-level tags** in `roles:` | `- { role: neutron, tags: neutron }` (`site.yml:690-691`). memcached has `tags: [memcache, memcached]` (`:428-429`); letsencrypt `tags: letsencrypt` (`:340-341`); the new valkey play `tags: valkey` (`:399-411`) | every task of the role. No role has a meta dependency (no role under `ansible/roles/` has a `meta/` directory), so nothing else is pulled in |
| **Task-level tags on `include_role`** | loadbalancer block: `include_role: {name: nova, tasks_from: loadbalancer}` with `tags: [nova, nova-api]` (`site.yml:252-258`) | the include statement only; see [§2.3](#23-include_role--tags-always-inside-the-haproxy-play-code) |
| **`tags: always`** | gather-facts and group_by plays (`gather-facts.yml:26, :62`, `site.yml:75`). `import_role: loadbalancer-config` in every one of the 38 `loadbalancer.yml` files; nova-cell's reaches it through `import_tasks: proxy_loadbalancer.yml` → looped `include_tasks: cell_proxy_loadbalancer.yml` → `import_role`, with `tags: always` at every level (`roles/nova-cell/tasks/loadbalancer.yml:56, :93, :130`; `proxy_loadbalancer.yml:19`; `cell_proxy_loadbalancer.yml:12`). `roles/opensearch/tasks/register.yml:7`. `rabbitmq-upgrade.yml:16` | runs regardless of `--tags`, unless the enclosing dynamic include is skipped |
| **Tags inside roles** | `roles/nova/tasks/stop.yml:7` (`tags: nova`). `roles/service-rabbitmq/tasks/main.yml:44-45` (`tags: [service-rabbitmq]`). `roles/service-images-pull/tasks/main.yml:17-18`, `roles/rabbitmq/tasks/precheck.yml:164` (`rabbitmq-ha-precheck`), `roles/rabbitmq/tasks/version-check.yml:80` (`rabbitmq-version-check`). **New in 2025.1:** `roles/nova-cell/tasks/version-check.yml:73` (`nova-libvirt-version-check`) and `:116` (`nova-libvirt-script-check`). `roles/common/tasks/main.yml:2` carries no tag | – |
| **Other playbooks** | `kolla-host.yml:13-14` (`baremetal`, role `openstack.kolla.baremetal`), `mariadb_backup.yml:9-10`, `mariadb_recovery.yml:9-10` (`mariadb`), `bifrost.yml:5-6` (`bifrost`) | – |

The full per-play tag list is generated in [Generated inventory
§1](../reference/generated-inventory.md#1-plays-executed-by-siteyml-in-order). Per-service cards (tags, task flow,
handlers, node types) are in [Components](../components/index.md). The output of `ansible-playbook --list-tags` against
the real 2025.1 `site.yml`, produced with ansible-core 2.18.20, is in
[list-tags-site.txt](../reference/listings/list-tags-site.txt). Per play it shows the *task tags* after inheritance:
`common` is a tag of the common play only (`site.yml:88-103`; listing lines 98-99), and the letsencrypt play shows
`TAGS: []` with task tag `letsencrypt` (listing lines 104-105).

---

## 2. Ansible 2.9 semantics that Kolla relies on

The heading keeps its Ussuri name for stable links. Kolla-Ansible 2025.1 installs with ansible-core 2.17 to 2.18
(`requirements.txt:14`); it no longer checks the version at run time (the 2024.1 `tools/kolla-ansible` check is gone
with the script). Everything below is read in ansible-core 2.18.20. Whether ansible-core 2.17 behaves the same is
[NOT AVAILABLE] (not studied).

### 2.1 Dynamic `include_tasks` and tag inheritance [CODE]

Every role starts with `include_tasks: "{{ kolla_action }}.yml"` (dynamic). In ansible-core 2.18, tasks inside a
dynamically included file:

- **do inherit** the tags of the enclosing *role* and *play*: `nova`, `neutron`, `common`, `haproxy`, …;
- **do not inherit** tags written on the `include_tasks` statement itself (they apply to the include only, unless
  `apply:` is used — Kolla never uses `apply:`).

In the source (ansible-core 2.18.20): without `apply:`, the include itself becomes the parent of the included blocks
(`lib/ansible/playbook/task_include.py:106-126`, used at `lib/ansible/plugins/strategy/__init__.py:866`). An include
is not statically loaded (`task_include.py:46-48`), so `Block._get_parent_attribute` skips it and takes the tags of
the include's own parent (`lib/ansible/playbook/block.py:309-327`), of the role and its dependency chain
(`block.py:328-349`) and of the play (`block.py:350-359`); `tags` is an `extend` attribute
(`lib/ansible/playbook/taggable.py:40`). The included tasks are then filtered on those tags
(`lib/ansible/plugins/strategy/linear.py:274`, `block.py:365-390`). Applied to Kolla 2025.1, where `common` is a
play of its own with `tags: [common]` (`site.yml:88-103`) and its role's `include_tasks` carries no tag
(`roles/common/tasks/main.yml:1-2`):

```text
--tags common            → the common play runs: the include_tasks and every task of the included file (play tag `common`)
--tags nova              → the common play is skipped (it carries only `common`); the nova plays' included tasks run
--tags service-rabbitmq  → nothing: the include that would load the tagged task does not carry the tag
```

Still holds in 2025.1: no role has a `meta/` directory, and `role: common` appears only in the common play
(`site.yml:103`).

The filter applies `--skip-tags` too (`taggable.py:79-90`), and there a tag written inside an included file does
work: the included task carries it, so `--skip-tags rabbitmq-version-check` drops the RabbitMQ version check
(`roles/rabbitmq/tasks/version-check.yml:2-83`, imported at `roles/rabbitmq/tasks/deploy.yml:2`) while `--tags
rabbitmq-version-check` alone runs nothing of it [CODE]. The same holds for the two new nova-cell checks: their own
failure messages tell you to skip `nova-libvirt-version-check` or `nova-libvirt-script-check`
(`roles/nova-cell/tasks/version-check.yml:65-68, :106-113`).

### 2.2 Handlers ignore tags [CODE]

A notified handler runs even if its own tags do not match `--tags`. Only the play's task blocks are filtered on tags
(ansible-core 2.18.20 `lib/ansible/executor/play_iterator.py:187-191`, `lib/ansible/playbook/block.py:365-390`); the
handler list is copied unfiltered (`play_iterator.py:193-198`) and, during a flush, a handler runs for every host it was
notified for, with no tag check (`play_iterator.py:424-438`; `lib/ansible/playbook/handler.py:55-59`). A
notification is first saved per host by name (`lib/ansible/plugins/strategy/__init__.py:647-663`,
`play_iterator.py:648-652`) and resolved to handlers at `meta: flush_handlers` (`lib/ansible/plugins/strategy/__init__.py:951-961`). A
notify reaches the handler of that name and every handler that `listen`s to that name (`lib/ansible/plugins/strategy/__init__.py:510-567`).
Tasks that a handler pulls in with `include_tasks` are not tag-filtered either: the strategy filters included blocks
only when the include is not a handler (`lib/ansible/plugins/strategy/linear.py:248-274`). This matters for etcd, whose
handlers are `include_tasks` statements with `listen` (`roles/etcd/handlers/main.yml:1-68`).

**Changed in 2025.1: `-t keystone` no longer restarts HAProxy.** In 2024.1 the `haproxy-config` task, imported under
`tags: always`, notified `Restart haproxy container`, and the handler then ran whatever the tag. In 2025.1
`roles/haproxy-config/tasks/main.yml` notifies nothing. The HAProxy restart is notified only by the loadbalancer role's
`check-containers`, which the loadbalancer play includes once, after all per-service includes, with no tag of its own
(`site.yml:319-324`); it inherits only the play's tags `haproxy`, `keepalived` and `loadbalancer` (`site.yml:115-118`).
Under `-t keystone` that include is not selected, so nothing notifies the HAProxy handler: the Keystone frontend file
under `services.d/` is rewritten, but HAProxy keeps the old configuration until a later run reaches the check step
(no tag, or `-t haproxy`, `keepalived` or `loadbalancer`) [CODE]. ansible-core lists the play that way: under
`--list-tasks -t nova` it shows only the `nova` and `nova-cell` includes ([list-tasks-nova.txt](../reference/listings/list-tasks-nova.txt),
lines 106-109). [NOT AVAILABLE] To be confirmed by the community. The restart sequence of an untagged or
`-t haproxy` run is in [§5](#5-role--handler-map-core-services).

### 2.3 `include_role` + `tags: always` inside (the haproxy play) [CODE]

The loadbalancer play (the "haproxy play" of Ussuri) holds per-service `include_role` statements, 38 in 2025.1
(`site.yml:122-318`; 39 in 2024.1, swift's is gone), then the loadbalancer role's `check-containers`
(`:319-324`). The includes are dynamic too. Their own tags (`keystone`, `nova`, …) only select the include statement:
the included role's blocks get the `include_role` as parent (ansible-core 2.18.20
`lib/ansible/playbook/role_include.py:100, :107, :114`), which is skipped as in
[§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), while `tags: always` matches any `--tags`
(`lib/ansible/playbook/taggable.py:68-69`). For the work inside to run, 37 of the 38 `loadbalancer.yml` files wrap a
single `import_role: loadbalancer-config` with `tags: always` (e.g. `roles/keystone/tasks/loadbalancer.yml:2-7`), and
`loadbalancer-config` imports `haproxy-config` (when `haproxy_config_install`, true for every project except `mariadb`
with ProxySQL) and `proxysql-config` (when `enable_proxysql`, **now `yes` by default**)
(`roles/loadbalancer-config/tasks/main.yml:2-8`, `roles/loadbalancer-config/defaults/main.yml:2`,
`group_vars/all.yml:958`). nova-cell's file reaches the same role through `import_tasks: proxy_loadbalancer.yml`, a
looped `include_tasks: cell_proxy_loadbalancer.yml` and then `import_role`
(`roles/nova-cell/tasks/cell_proxy_loadbalancer.yml:3-12`), with `tags: always` at every level, so the effect is the
same. Net effect: `-t <svc>` writes that service's HAProxy (and ProxySQL) config on all `loadbalancer` hosts, and,
changed in 2025.1, does not restart HAProxy ([§2.2](#22-handlers-ignore-tags-code)).

### 2.4 Loop-notify is gone in 2025.1 [CODE]

The Ansible behaviour is unchanged: in ansible-core 2.18.20, when a looped task reports changed, the notify list of
*every* executed item is saved (`lib/ansible/plugins/strategy/__init__.py:640-653`; `_ansible_notify` is attached to
every executed item, `lib/ansible/executor/task_executor.py:851`; the loop is changed if any item changed,
`task_executor.py:136-140`). In 2024.1 Kolla's `config.yml` and `check-containers.yml` looped over `<role>_services`
with `notify: "Restart {{ item.key }} container"`, so one changed item restarted every container of the role on that
host.

2025.1 no longer relies on it. The shared `service-check-containers` role compares every container in one loop that
notifies nothing (`roles/service-check-containers/tasks/main.yml:4-29`), then a separate, non-looped task notifies a
list built from the changed results only:
`container_check.results | select('changed') | map(attribute='item.key')` → `Restart <key> container` (`:34-41`).
The config tasks no longer notify at all (two exceptions, see [Conventions](../start/conventions.md#operation-impact-classes),
row `writes-config`). So **a change that concerns one container restarts that container only.**

Applied to the real playbook [CODE]. An override that only touches `/etc/kolla/config/nova/nova-compute.conf` changes
only nova-compute's `nova.conf` (`roles/nova-cell/tasks/config.yml:120-136`, source at `:129`). `kolla_set_configs
--check` in `nova_compute` then exits 1 (kolla `docker/base/set_configs.py:41-44, :186-191, :253-255, :660-662`), so
its `compare_container` result is changed (`module_utils/kolla_container_worker.py:58-65`,
`module_utils/kolla_docker_worker.py:146-181`, `library/kolla_container.py:421-422`). The other items on a compute host
with the defaults (`enable_nova_libvirt_container` true for the default `kvm`, `enable_nova_ssh: yes`,
`enable_nova_fake: no`; `group_vars/all.yml:945, :947, :980, :1253`) are `nova-libvirt` and `nova-ssh`
(`roles/nova-cell/defaults/main.yml:5-23`), whose files did not change, so the handlers restart **`nova_compute`
only**, on every compute host the run reaches. A scheduler-only override likewise restarts `nova_scheduler` only
(`roles/nova/tasks/config.yml:56-69`), not `nova_api` as in 2024.1.

Impact analysis in [Operations](../operations/index.md). [NOT AVAILABLE] Confirmation on a lab that only the changed
container restarts (to be confirmed by the community).

### 2.5 `run_once` with `serial` [CODE]

With `kolla_serial` > 0, a `run_once` task runs once **per batch**, not once per play: each batch is a separate run of
the play (ansible-core 2.18.20 `lib/ansible/executor/playbook_executor.py:183-191`), and `run_once` only ends the host
loop inside that run (`lib/ansible/plugins/strategy/linear.py:178, :205-206`). This applies to bootstrap containers,
Keystone registration, DB creation and the new nova-cell version check. It is not harmful for idempotent steps, but it
multiplies the number of DB-sync containers and Keystone API calls ([fact sheet C, cross-cutting table][sheet-c-0]).
**Changed in 2025.1:** only the commands that do not set `kolla_serial` themselves can be batched this way (`deploy`,
`deploy-containers`, `pull`, `stop`, …); `reconfigure` and `upgrade` always run with `kolla_serial=0`
([Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order)).

With `kolla-ansible deploy -e kolla_serial=1` and the three controllers of the `multinode` inventory
(`inventory/multinode:3-6`, `:99-100`, `:226-227`) [CODE]:

- `nova_api_bootstrap` (`run_once`, no `delegate_to`, `roles/nova/tasks/bootstrap_service.yml:2-21`) runs 3 times,
  once per controller batch, and each time on that batch's host (once more when `map_cell0` reports changed,
  `roles/nova/tasks/map_cell0.yml:66-67`).
- The `map_cell0` block (`run_once`, `roles/nova/tasks/map_cell0.yml:63`) runs 3 times; it is delegated to the first
  `nova-api` host every time (`map_cell0.yml:64`).
- The compute registration wait plus `list_cells` run once per batch that holds a compute: they are gated on the batch's
  first compute and delegated to the first conductor (`roles/nova-cell/tasks/wait_discover_computes.yml:42-43, :88-90`;
  `discover_computes.yml:5, :21`; `roles/nova-cell/tasks/deploy.yml:21-39`).
- Nova containers restart strictly one host at a time, since each one-host batch finishes before the next starts.

The MariaDB and RabbitMQ restart plays do not use `kolla_serial`: they have their own `serial: "33%"`
(`mariadb.yml:24, :42`; `rabbitmq.yml:36`), which is one host per batch for up to five hosts (a percentage rounds
down with a minimum of 1, `lib/ansible/utils/helpers.py:23-32`, used at `playbook_executor.py:290`).

The etcd play has no `serial` (`site.yml:485-496`), so `kolla_serial` does not batch it. Its handlers order the
restarts instead: they look up the leader, restart the non-leaders through an `include_tasks` looped over `0..3` with
`groups.etcd.index(inventory_hostname) % 4 == item` (outside `upgrade`), then the leader, whose handler is defined
after them (`roles/etcd/handlers/main.yml:9-15, :38-61`). On `upgrade`, the non-leader handler loops over `groups.etcd`
without using `item` (`:26-34`); its comment says "one by one", but the actual order across hosts is [NOT AVAILABLE].

Every play also sets `max_fail_percentage`, default 100 (e.g. `site.yml:96-99`). It counts the failures of the
current batch only: each batch is a separate `TaskQueueManager.run()` (`playbook_executor.py:183-191`), which clears
the failed hosts first (`lib/ansible/executor/task_queue_manager.py:334`), and the check compares them with the
batch size (`linear.py:336-347`). With 100 it never stops a play early [CODE].

### 2.6 `--list-tasks` is not usable for Kolla [CODE]

Because of [§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code), `ansible-playbook site.yml --list-tasks -t nova`
lists only `include_tasks` placeholders for each role: the listing walks only the statically compiled play
(ansible-core 2.18.20 `lib/ansible/cli/playbook.py:186-218`), while dynamic includes are loaded at run time
(`lib/ansible/plugins/strategy/linear.py:237-274`). `config.yml` and `check-containers.yml` are invisible: the `Apply
role nova` and `Apply role nova-cell` plays show one `include_tasks` each
([list-tasks-nova.txt](../reference/listings/list-tasks-nova.txt), lines 211-217). Plays whose host pattern depends on
the `group_by` groups (`&enable_nova_True`) also resolve to **0 hosts** at list time. Those groups are created at run
time (`[WARNING]: Could not match supplied host pattern, ignoring: enable_nova_True`, listing line 51), and an `&`
pattern keeps only the hosts that match it (`lib/ansible/inventory/manager.py:446-448`). The same holds for the
MariaDB and RabbitMQ restart plays, whose groups (`mariadb_restart`, `rabbitmq_restart`; listing lines 20 and 33) only
the handlers create. The 2025.1 CLI cannot produce the listing at all: its `--list-tasks` option is documented as
having no effect ([Ansible listings](../reference/listings/index.md)). `--check` is no substitute: `kolla_container`
does not declare check-mode support (`library/kolla_container.py:351-355`), so its module exits as skipped under
`--check` (ansible-core 2.18.20 `lib/ansible/module_utils/basic.py:447-448`) [CODE], and whether such a run is usable
is [NOT AVAILABLE] ([Predict and inspect a run](../operations/predict-a-run.md), [Open questions
Q9](../troubleshooting/open-questions.md#q9)). To predict restarts, use `genconfig` plus `kolla_set_configs --check`
(end of [§3.1](#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites)), or the new `kolla-ansible
check` to see which containers are missing, stopped or unhealthy.

---

## 3. What a tag really executes (master table)

"Target hosts" assumes the 2025.1 `multinode` example inventory. "Containers" lists those that *can* be restarted or
recreated, **only if** a parameter, image or config change is detected for **that** container: in 2025.1 a restart
handler runs only when the shared check step reports that container changed
([§2.4](#24-loop-notify-is-gone-in-20251-code)) [CODE]. `compare_container` reports *changed* only when the container
is missing, differs from the task in a compared parameter (image, volumes, environment, dimensions, command,
privileges, labels, healthcheck, state, …), its systemd unit file is missing or differs, or `kolla_set_configs --check`
reports drift (`module_utils/kolla_container_worker.py:58-89`; `module_utils/kolla_systemd_worker.py:155-168`) [CODE].
With Docker, drift is exit 1 or 137 or a Docker client error (`module_utils/kolla_docker_worker.py:146-181`); with
Podman, exit 1, a container that is not running, or a Podman client error
(`module_utils/kolla_podman_worker.py:524-552`). **At the first run after an upgrade from 2024.1**, the 2025.1 systemd
unit and, with Docker on hosts outside the Red Hat family, the new default `ulimits` make containers differ whatever
the tag ([Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)).
[NOT AVAILABLE] Whether, on an unchanged cloud and apart from the exception below, nothing restarts.

The kolla source shows one exception, still present in 2025.1: `kolla_set_configs --check` exits 1 on every run for a
`config_files` entry with `preserve_properties` and no `perm`, as soon as a matching file or subdirectory has been
copied (the expected `perm` is then empty and never equals the actual mode; kolla `docker/base/set_configs.py:192-198,
:219-224`; [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
So `prometheus_server` restarts on every deploy/reconfigure whenever `{{ node_custom_config }}/prometheus/extras/`
holds files already copied into the container (`roles/prometheus/templates/prometheus-server.json.j2:16-21`;
`roles/prometheus/tasks/deploy.yml:2-9`). A newly added extras file makes the check fail too: a source without a
destination is a plain mismatch (`set_configs.py:180-182`), so `--check` exits 1 and `prometheus_server` restarts
([Predict and inspect a run](../operations/predict-a-run.md)).

"common" means the `common` role (fluentd/cron/kolla_toolbox config, `kolla.target`, container check, `kolla_logs`
volume). It runs only in the common play (`site.yml:88-103`), on the `cron`, `fluentd`, `kolla-logs` and
`kolla-toolbox` groups, which are all children of `common` (`inventory/multinode:49-54, :202-212`). No other row runs
it. A tag that selects a loadbalancer include rewrites that service's frontend but, in 2025.1, does not restart
`haproxy` ([§2.2](#22-handlers-ignore-tags-code)).

| Tag | Plays / roles selected | Tasks executed | Target hosts | Containers that can restart | Other side effects | Potential impact |
|---|---|---|---|---|---|---|
| *(no tag)* | all 71 plays ([Generated inventory §1](../reference/generated-inventory.md#1-plays-executed-by-siteyml-in-order)) | everything for `kolla_action` | all | all | all bootstrap/DB-sync containers, Keystone registration of all services | Full blast radius |
| `common` | the common play (`site.yml:88-103`) | config (`kolla.target`, `config.json`, `fluentd.conf`, cron logrotate, toolbox files; with Podman, `/etc/tmpfiles.d/kolla.conf`, `roles/common/tasks/config.yml:42-52`), check-containers, `kolla_logs` volume, flush (`roles/common/tasks/deploy.yml:2-9`) [CODE] | every host of the `common` group (control, network, compute, storage, monitoring) | `fluentd`, `kolla_toolbox`, `cron` | – (changed in 2025.1: no fluentd image pull) | Every host at once unless `-e kolla_serial=N` on a command that accepts it; the containers are not on the VM or API path |
| `haproxy` (also `keepalived`, `loadbalancer`: same play) | loadbalancer play (`site.yml:105-327`): loadbalancer role (config-host, config, check-containers, no flush), all 38 loadbalancer includes evaluated, but only those of enabled services run (each except placement's has a `when` on `enable_*` flags), then the loadbalancer `check-containers` step (not on `genconfig`); the whole block only with `enable_haproxy` and `kolla_action` in deploy/reconfigure/upgrade/config (`site.yml:319-327`) | sysctl (through the `sysctl` role), keepalived kernel module, `haproxy.cfg`, `keepalived.conf`, keepalived checks, ProxySQL config (on by default), the single external frontend map when enabled, certs, `haproxy-ssh` files with letsencrypt, the `services.d/*.cfg` of every enabled service (`roles/loadbalancer/tasks/config-host.yml`, `config.yml`) | `loadbalancer` hosts (network in `multinode`, `inventory/multinode:84-85`) | `haproxy`, `keepalived`, `proxysql`, `haproxy_ssh` (with `enable_letsencrypt`) | – | API and DB path interruption if anything changed; hosts without the VIP first, then the VIP holder ([§5](#5-role--handler-map-core-services)); whether the VIP moves is [NOT AVAILABLE] ([A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour)). The letsencrypt play is **not** selected (it carries only the role tag `letsencrypt`). **This is now the tag that applies frontend changes written by earlier `-t <svc>` runs** |
| `<svc>` (e.g. `keystone`, `glance`, `cinder`, `heat`, `placement`; `horizon` differs, see below the table) | loadbalancer play (that service's include only) + the service play | `services.d/<svc>*.cfg` (and ProxySQL user/rules files); register, config, check-containers, bootstrap of the service | loadbalancer hosts + service hosts | the service's containers that changed (one at a time per container, all hosts of the play at once); **not `haproxy`** (changed in 2025.1, [§2.2](#22-handlers-ignore-tags-code)) | DB sync container, Keystone registration | Service API outage during the parallel restart of the changed containers. A changed frontend is **not applied** until a run with `-t haproxy` or no tag |
| `letsencrypt` | loadbalancer letsencrypt include + the letsencrypt play (`site.yml:329-341`), both only with `enable_letsencrypt` (default `no`, `group_vars/all.yml:913`) | haproxy-config for the letsencrypt frontend; letsencrypt role: config (`letsencrypt-webserver.conf`, lego files), check-containers, flush (`roles/letsencrypt/tasks/deploy.yml:2-7`, `config.yml:2-50`) | loadbalancer hosts; the letsencrypt play's hosts are `letsencrypt`, a child of `loadbalancer` (`inventory/multinode:188-189`) | `letsencrypt_webserver`, `letsencrypt_lego` | – | [NOT AVAILABLE] what a restart of the letsencrypt containers does to a certificate renewal in progress. `haproxy_ssh` is in the loadbalancer play, not under this tag |
| `valkey` (new) | the valkey play (`site.yml:399-411`), only with `enable_valkey` | valkey role | `valkey` hosts | valkey containers | – | See [Tag index](tag-index.md) and [Components](../components/index.md) |
| `nova` | loadbalancer (nova + nova-cell includes), all 10 `nova.yml` plays | API/cell0/cell DB bootstrap, cell create/update, nova + nova-cell config/check (with the new libvirt version and image checks), discovery, scheduler SIGHUP; reload/online-migration plays are no-ops except on `upgrade` | loadbalancer, `nova-api`, `nova-scheduler`, `nova-conductor`, consoles, **every `compute`** | the nova API/scheduler/conductor/metadata/console containers that changed, and on **every compute**, `nova_compute`, `nova_libvirt` or `nova_ssh` if that container changed | 6 one-shot container runs on `control01` when cell0 is mapped with an unchanged connection and the cell is unchanged (API DB sync, map_cell0, list_cells for cell0, cell DB sync, list_cells ×2) [CODE] (`roles/nova/tasks/bootstrap.yml:54-56`, `map_cell0.yml:2-64`, `roles/nova-cell/tasks/bootstrap.yml:41-43`, `create_cells.yml:2`, `discover_computes.yml:5`), plus the libvirt check containers; RabbitMQ vhost/user for the cell; `kill -HUP` of nova_scheduler on every scheduler | See [Nova deep dive](../components/nova-deep-dive.md), [Reconfigure Nova](../operations/reconfigure-nova.md) |
| `nova-api` | loadbalancer nova include, API DB bootstrap play, nova play, scheduler cell-cache refresh, API reload/migrations | haproxy-config for the nova API/metadata frontends; nova_api + nova_cell0 DB/user creation and API DB sync on the first host of the play (`run_once`), `map_cell0` delegated to `nova-api[0]`; nova role: Keystone registration, config, check-containers, flush (`roles/nova/tasks/deploy.yml:2-9`); scheduler SIGHUP | controllers + loadbalancer | nova_api, nova_metadata, nova_scheduler, nova_super_conductor (only with `enable_cells`), each only if it changed | API DB sync, map_cell0 | Does **not** touch computes |
| `nova-cell` | loadbalancer nova-cell include, cell DB bootstrap, nova-cell play, cell reload/migrations | haproxy-config for the console-proxy frontends; on the first conductor: cell DB/user, RabbitMQ vhost/user (gated on the first conductor but run via `delegate_to` on the first host of the cell RPC/notify group, `rabbitmq[0]` by default, `roles/nova-cell/tasks/rabbitmq.yml:3-29`), cell DB sync, cell create/update; nova-cell role: version check, config-host, config, check-containers, flush, then compute discovery delegated to the first conductor (`roles/nova-cell/tasks/deploy.yml:5-39`) | conductors, consoles, **all computes** | nova_conductor, consoles, nova_compute, nova_libvirt, nova_ssh, each only if it changed | cell DB sync, cell create/update, RabbitMQ vhost/user for the cell, discovery | Touches every compute |
| `nova-bootstrap`, `nova-api-bootstrap`, `nova-cell-bootstrap` | the two bootstrap plays (`nova.yml:29-100`) | DB creation, DB sync containers, cell mapping | all `nova-api` hosts (API play) and all `nova-conductor` hosts (cell play); DB tasks and one-shot containers: the first `nova-api` host of the play, `nova-conductor[0]` | none: `include_role` compiles only the role and its dependencies (ansible-core 2.18.20 `lib/ansible/playbook/role_include.py:86-87, :100-107`, `lib/ansible/playbook/role/__init__.py:589-611`), and no role has dependencies; one-shot bootstrap containers only | RabbitMQ vhost/user for the cell | Schema changes only if images are newer |
| `nova-reload`, `nova-api-reload`, `nova-cell-reload` | reload plays (`nova.yml:180-253`) | `recreate_or_restart` of nova services **only when `kolla_action == upgrade`** | as named | on upgrade: all nova services | – | No-op outside upgrade |
| `nova-online-data-migrations` (+ `-api-`, `-cell-`) | `nova.yml:258-302` (both plays `any_errors_fatal: true`, `:270, :295`) | `nova-manage db online_data_migrations` | `nova-api[0]`, `nova-conductor[0]` | – | upgrade only | – |
| `nova-refresh-scheduler-cell-cache` | `nova.yml:152-172` (`import_role: nova, tasks_from: refresh_scheduler_cell_cache`) | `kill -HUP` of `nova_scheduler` (`roles/nova/tasks/refresh_scheduler_cell_cache.yml:4-12`) | nova-scheduler hosts | `nova_scheduler` only gets SIGHUP (no restart) | – | Runs on **every** deploy/reconfigure with `nova` or `nova-api` (`nova.yml:157-160, :170-172`); it adds only the signal |
| `neutron` | loadbalancer neutron include, neutron play (hosts include **`compute`** and `manila-share`, `site.yml:669-691`) | plugin/agent check, register, config-host, config, check-containers, DB and DB-user creation, `bootstrap_neutron` DB-sync container on every deploy and reconfigure (`roles/neutron/tasks/deploy.yml:2-23`, `bootstrap.yml:38`, `bootstrap_service.yml:2-21`, no `when`) | loadbalancer, neutron-server, network agent hosts, **every compute** | neutron_server and the agents that changed | DB sync container | OVS agent restarts on computes, L3/DHCP agent restarts on network nodes, when they changed; [NOT AVAILABLE] whether flows are resynced and traffic is interrupted ([Reconfigure Neutron](../operations/reconfigure-neutron.md)) |
| `openvswitch` | openvswitch play, only while `enable_ovs_dpdk` is `no` (`site.yml:605-618`; `ovs-dpdk` has its own play and tag); **now before the Nova plays** | config-host, config, check-containers, flush, **post-config**: `system-id`, `hostname` and `hw-offload` set through `kolla_toolbox` + `openvswitch_db`; bridges and ports through `kolla_toolbox` + `openvswitch_bridge` / `openvswitch_port` (`roles/openvswitch/tasks/deploy.yml:2-11`, `roles/openvswitch/tasks/post-config.yml:3-53`) | `openvswitch` group (network + **compute** + manila-share, `inventory/multinode:105-108`) | `openvswitch_db`, `openvswitch_vswitchd` | a changed `system-id`/`hostname`/`hw-offload` notifies `Restart openvswitch-vswitchd container`, run at the end of the play (`roles/openvswitch/tasks/post-config.yml:22-23`) | [NOT AVAILABLE] whether a vswitchd restart interrupts **all VM traffic** on that host ([Risk register R7](risk-register.md#r7)) |
| `ovn` (also `ovn-controller`, `ovn-db`: one play each) | ovn-controller play and ovn-db play (`site.yml:635-665`), **now before the Nova plays** | ovn-controller: config, check-containers, chassis setup (`br-int`, then the `external_ids` keys through `openvswitch_db`, `roles/ovn-controller/tasks/setup-ovs.yml:2-49`), flush; ovn-db: cluster lookup, config, check-containers, flush, DB bootstrap (`roles/ovn-db/tasks/deploy.yml:2-22`) | ovn-controller (**every compute and network**, `inventory/multinode:579-587`), OVN DB hosts (control) | `ovn_controller`; `ovn_nb_db`, `ovn_sb_db`, `ovn_northd` (and the SB relay, [OVN](../components/ovn.md)) | sets or removes `ovn-cms-options` from `ovn_cms_opts` (`roles/ovn-controller/tasks/setup-ovs.yml:48`) | [A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable) |
| `mariadb` | loadbalancer mariadb include, the five `mariadb.yml` plays (`mariadb.yml:3-92`) | cluster lookup, bootstrap or recovery when needed, config, check-containers; the handlers only sort hosts into `mariadb_restart` / `mariadb_start` (`roles/mariadb/handlers/main.yml:59-74`), and the restart plays then restart them in `serial: "33%"` batches, each waiting for the port and WSREP `Synced` (`roles/mariadb/tasks/restart_services.yml:2-53`); post-config | mariadb hosts | mariadb (one host per batch with three nodes), mariadb_clustercheck when enabled | – | [B §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb) |
| `rabbitmq` | loadbalancer include, the three `rabbitmq.yml` plays (`rabbitmq.yml:3-70`) | haproxy-config for the `rabbitmq_management` frontend; version check (`roles/rabbitmq/tasks/deploy.yml:2`, `version-check.yml:2-83`), removal of the `ha-all` policy, now included on every run (`deploy.yml:4`), config (`config.json`, `rabbitmq-env.conf`, `rabbitmq.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`, `enabled_plugins`; `roles/rabbitmq/tasks/config.yml:2-101`), check-containers, bootstrap; the handler only adds the host to `rabbitmq_restart` (`roles/rabbitmq/handlers/main.yml:2-4`); restart play: drain, restart, `rabbitmqctl wait`, `serial: "33%"`; post-config | rabbitmq hosts | rabbitmq (one by one with three nodes) | `rabbitmq_version_check` one-shot | [B §2](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#2-rabbitmq-ansiblerolesrabbitmq-used-twice) |
| `etcd` (when `enable_etcd`, default `no`, `group_vars/all.yml:878`) | loadbalancer etcd include + the etcd play (`site.yml:485-496`, no `serial`) | config, check-containers, bootstrap (cluster lookup; facts that notify the bootstrap handlers), flush (`roles/etcd/tasks/deploy.yml`) | loadbalancer hosts; `etcd` hosts (control, `inventory/multinode:62-63`) | `etcd`: non-leaders through the `% 4` loop, the leader last ([§2.5](#25-run_once-with-serial-code)) | cluster bootstrap or member addition when volumes are new; removal of deleted members (`roles/etcd/handlers/main.yml:2-7, :17-24, :63-68`) | Not batched by `kolla_serial`; [NOT AVAILABLE] whether clients lose the cluster during the restarts |
| `memcached` / `memcache` | memcached play (`memcache` does **not** select the loadbalancer include) | config dir + `config.json`, check-containers. `memcached` also selects the loadbalancer include, which renders a frontend only with `enable_haproxy_memcached` (default `no`, `group_vars/all.yml:850`) | memcached hosts | memcached (all at once). **Changed in 2025.1:** a memcached setting is in the `command` of `config.json`, which `--check` now compares, so a setting change restarts it even after `genconfig` ([Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)) | – | [NOT AVAILABLE] whether the restart empties the token cache and the Horizon sessions kept there ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) |
| `chrony` | **none**: `site.yml` has no chrony play and there is no chrony role (`ansible/roles/`) | only the `always` plays (fact gathering, `group_by`) | – | none | – | Not a way to reach every host; use `-t common` ([§4](#4-practical-consequences)) |
| removed services: `swift` (removed in 2025.1), and from earlier releases `freezer`, `monasca`, `murano`, `sahara`, `senlin`, `solum`, `vitrage`, `kafka`, `storm`, `zookeeper`, `outward-rabbitmq` | **none**: their roles are gone from `ansible/roles/` and no playbook has a play for them | only the `always` plays | – | none: no tagged run stops or removes their containers [CODE] | – | [NOT AVAILABLE] what happens to swift containers left on a host upgraded from 2024.1 ([Swift](../components/swift.md)) |
| `iscsi` | iscsi play (`site.yml:454-467`), only where `enable_iscsid` is true (default: `enable_cinder` and `enable_cinder_backend_iscsi`, `group_vars/all.yml:911`) | config-host (load and persist `configfs`, `roles/iscsi/tasks/config-host.yml:2-10`), config dirs + `config.json`, check-containers, flush (`roles/iscsi/tasks/deploy.yml`) | iscsid (compute + storage + ironic), tgtd (storage) (`inventory/multinode:307-313`) | iscsid, tgtd | – | Volume attach path on computes ([D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)) |
| `service-rabbitmq` | the RabbitMQ user/vhost blocks inside roles | **nothing** on its own (inside dynamic includes) | – | – | – | Not usable as a selector |
| `baremetal` | `kolla-host.yml` only (role `openstack.kolla.baremetal` from ansible-collection-kolla) | host preparation: `/etc/hosts`, packages, the container engine, `kolla` user, engine SDK ([fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md)) | `baremetal` group (all node groups in `multinode`, kolla-ansible `ansible/inventory/multinode:35-40`) | **Docker daemon restart if `daemon.json` changed** (ansible-collection-kolla's `roles/docker/tasks/config.yml:48-53`, `roles/docker/handlers/main.yml:10-15`) | packages, users, `/etc/hosts` | [E §1–3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#1-ansiblekolla-hostyml-the-bootstrap-servers-command) |

`horizon` follows the `<svc>` row without registration and, by default, without bootstrap. The role has no
`register.yml`, so it is never registered in Keystone. Its DB creation and `bootstrap_horizon` DB sync run only when
`horizon_backend_database` is true (default `false`, `group_vars/all.yml:1267`). With defaults, `-t horizon` runs the
loadbalancer horizon include, config, check-containers and, if the container changed, the horizon restart handler.

### 3.1 Per-tag answers: files, VMs, APIs, networking/storage, safety, prerequisites

This table answers the remaining per-tag questions. What runs, which services are affected and which containers can
restart are in the master table above. Which handlers can fire is in [§5](#5-role--handler-map-core-services): handlers
fire only for containers reported changed, and tags never filter them ([§2.2](#22-handlers-ignore-tags-code)). "R*n*"
refers to [Risk register](risk-register.md). Everything assumes a change was detected. A "none" or "none directly"
under Running VMs or Networking / storage means that the tag cannot restart `nova_compute`, `nova_libvirt`,
`nova_ssh`, an Open vSwitch, OVN or Neutron agent container, `iscsid` or `tgtd` [CODE]; whether its restarts reach
running VMs or traffic another way is [NOT AVAILABLE] ([Limits of the
study](../reference/method-and-limits.md#limits-of-this-study)).

| Tag | Config files that can change | Running VMs | API availability | Networking / storage | Safe on its own? | Prerequisites |
|---|---|---|---|---|---|---|
| `haproxy` | `haproxy.cfg`, `services.d/*.cfg` of enabled services, `keepalived.conf`, keepalived checks, ProxySQL config, single external frontend map when enabled, TLS PEMs, `haproxy-ssh` files with letsencrypt, sysctl | no direct effect; [NOT AVAILABLE] whether instance metadata requests, which the metadata agents send to nova through the internal FQDN, fail while HAProxy is down | **yes**: HAProxy is stopped and started (never reloaded); hosts that do not hold the VIP go first and are waited for, then the VIP holder's HAProxy is stopped and started (`roles/loadbalancer/handlers/main.yml:54-68, :90-120, :181-195, :226-255`), and all APIs and the DB path go through it (ProxySQL too, by default); [NOT AVAILABLE] whether established connections are cut and whether keepalived drops or moves the VIP while the master's HAProxy is down ([R8](risk-register.md#r8)) | control plane only | yes if nothing reports a change; with a change, prefer a window. It also applies every frontend left pending by earlier `-t <svc>` runs | facts of every backend host; certificates if TLS is on |
| `<svc>` API service (`keystone`, `glance`, `cinder`, `heat`, `placement`, `horizon`) | service configs on its hosts, its `services.d` frontend (not applied until `-t haproxy` or an untagged run) | none for keystone/heat/placement/horizon; glance/cinder transfers in progress are SIGKILLed after 60 s (`docker_graceful_timeout`, `group_vars/all.yml:148`, [R24](risk-register.md#r24)) | **yes**: the changed containers restart on all the service's hosts at once; [NOT AVAILABLE] whether other APIs fail authentication while Keystone restarts ([R19](risk-register.md#r19)) and whether scheduling stops while Placement restarts ([Nova deep dive §3](../components/nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate) item 4) | cinder: volume operations; `iscsid` and `tgtd` are in the `iscsi` play, not under `-t cinder` (`site.yml:454-467`) | yes, it is the intended unit; it still runs Keystone registration and DB sync (horizon: neither, by default). `reconfigure` cannot batch it; use `deploy -e kolla_serial=N` or `--limit`; the glance file backend has one host ([R20](risk-register.md#r20)). A changed frontend (new endpoint, TLS change) needs a follow-up `-t haproxy` | MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP |
| `letsencrypt` | letsencrypt `config.json` files, `letsencrypt-webserver.conf`, lego files, letsencrypt frontend (`roles/letsencrypt/tasks/config.yml:2-50`) | none | none directly; the letsencrypt frontend is applied only by a later `-t haproxy` or untagged run | none | yes; it touches only loadbalancer hosts | `enable_letsencrypt`; HAProxy |
| `nova` | API and cell `nova.conf`, `config.json`, policy, libvirt (`libvirtd.conf`, `qemu.conf`, SASL), nova-ssh files, Ceph keyrings when enabled, nova frontends | [CODE] `nova_libvirt` restarts only if its own container changed (a libvirt setting, a new image, the 2025.1 unit or `ulimits` at the first run after the upgrade) ([R1](risk-register.md#r1)); [NOT AVAILABLE] whether live migrations in progress fail and whether running VMs survive ([Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), [Reconfigure Nova §5](../operations/reconfigure-nova.md#5-running-vms-live-migration-scheduling)) | the changed nova API, metadata, scheduler and conductor containers restart at once; [NOT AVAILABLE] whether instance actions fail meanwhile | [NOT AVAILABLE] whether attach/detach and port binding in flight fail; no OVS change | only with batching and a window; prefer `genconfig` + `deploy-containers --limit` ([Write config first, apply in controlled batches §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). The new version checks fail the play on a libvirt downgrade or an old `nova_libvirt` image | MariaDB, RabbitMQ, memcached, Keystone, Placement, Glance, Neutron registered |
| `nova-api` | API-side `nova.conf`, `config.json`, policy, nova frontends | none | the changed nova API, metadata, scheduler, super-conductor (with `enable_cells`) containers | none | yes; does not touch computes | as `nova` |
| `nova-cell` | cell `nova.conf`, libvirt, nova-ssh and Ceph files on computes and conductors, console frontends | **yes**, as `nova` | conductors and console proxies | as `nova` | as `nova` | the API DB and cell0 mapping (`nova-api`/`nova`), RabbitMQ |
| `neutron` | `neutron.conf`, `ml2_conf.ini`, `openvswitch_agent.ini`, `l3_agent.ini`, `dhcp_agent.ini`, `metadata_agent.ini` (+ enabled features), neutron frontend | **yes** when the agent changed: OVS agent restart on computes ([NOT AVAILABLE] whether and how it resyncs flows, and whether traffic is lost), L3/DHCP/metadata agent restarts on network nodes; running L3 agents restart in the order of the host list, spaced by `neutron_l3_agent_failover_delay` per host (default `0`, so no spacing; `roles/neutron/handlers/main.yml:82-135`, `roles/neutron/defaults/main.yml:626`); with `enable_neutron_agent_ha`, the L3 agent wrapper runs `neutron-netns-cleanup` before the agent starts, and what that command deletes is [NOT AVAILABLE] ([R6](risk-register.md#r6)) | neutron-server restarts on all controllers at once when it changed | **networking: yes** ([Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking)); storage: no | risky without batching ([R5](risk-register.md#r5), [R6](risk-register.md#r6)) | Open vSwitch or OVN running, MariaDB, RabbitMQ, Keystone |
| `openvswitch` | `config.json` of `openvswitch_db`/`openvswitch_vswitchd`; `system-id`, `hostname` and `hw-offload` (through `openvswitch_db`), and bridges and ports on network nodes (and on computes when `computes_need_external_bridge`) | [NOT AVAILABLE] whether running VMs are affected if `openvswitch_vswitchd` restarts or is recreated, e.g. whether all VM traffic on the host stops until flows are reinstalled ([R7](risk-register.md#r7)). The start scripts of 2024.1 are gone; the start path is on the [Open vSwitch](../components/openvswitch.md) page | none | **networking: yes** | yes if unchanged; a changed `system-id`, `hostname` or `hw-offload` restarts `openvswitch_vswitchd` (`roles/openvswitch/tasks/post-config.yml:22-23`); whether the `openvswitch_db`, `openvswitch_bridge` and `openvswitch_port` modules, run inside `kolla_toolbox`, report *ok* when the value is already set is [NOT AVAILABLE] (the modules are not in the studied sources); image changes per host batch | `openvswitch` kernel module |
| `ovn` | `config.json` of the OVN containers; chassis `external_ids` (`ovn-cms-options` set from `ovn_cms_opts` or removed) | [NOT AVAILABLE] whether an ovn-controller restart re-programs flows on the host | NB/SB DB restarts interrupt neutron-server's OVN driver | **networking: yes** | check manual `ovn-cms-options` first ([A §5.8](../reference/factsheets/a-infra-lb-ovn.md#58-operationally-notable)) | Open vSwitch |
| `mariadb` | `galera.cnf` (lists all nodes), `config.json`, clustercheck files when enabled, `wsrep-notify.sh` | none directly | restart in `serial: "33%"` batches of the hosts the handlers put in `mariadb_restart` (one host at a time with three nodes, `mariadb.yml:18-34`); with ProxySQL, the default in 2025.1, the writer is chosen by ProxySQL ([fact sheet B](../reference/factsheets/b-mariadb-rabbitmq-keystone.md)); [NOT AVAILABLE] in which batch the writer restarts ([R9](risk-register.md#r9)) | DB only | only on a healthy, fully synced cluster | every node `Synced` |
| `rabbitmq` | `rabbitmq.conf`, `rabbitmq-env.conf`, `erl_inetrc`, `advanced.config`, `definitions.json`, `enabled_plugins`, `config.json` | none directly; [NOT AVAILABLE] whether nova-compute and the agents lose RPC while their broker restarts | restarts are one by one with three nodes: each node is drained into maintenance mode, restarted and waited for (`rabbitmq.yml:30-49`; `roles/rabbitmq/tasks/restart_services.yml:10-49`); [NOT AVAILABLE] whether RPC-backed API calls time out meanwhile | none directly; [NOT AVAILABLE] whether the agents reconnect by themselves | yes on a healthy cluster; membership changes are [R3](risk-register.md#r3) | no partitions, all nodes running |
| `etcd` | `config.json` and environment of `etcd` | none | etcd restarts in handler order, not in `kolla_serial` batches ([§2.5](#25-run_once-with-serial-code)); [NOT AVAILABLE] whether its clients fail meanwhile | none directly | only on a healthy cluster; the `upgrade` restart order is [NOT AVAILABLE] | `enable_etcd` |
| `memcached` / `memcache` | `config.json` (its `command` holds every setting) | none | memcached restarts on all memcached hosts at once; [NOT AVAILABLE] whether that empties the token cache (with extra load on Keystone) and loses the Horizon sessions kept in memcached ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) | none | yes, off-peak | none |
| `chrony` | none: no chrony play | none | none | none | does nothing | – |
| `common` | `kolla.target`, `config.json`, `fluentd.conf`, cron logrotate config (lists services by their `enable_*` flags), kolla_toolbox files, on **every** host of `common` [CODE] (`roles/common/tasks/config.yml`) | none | none (common containers only) | none | yes; the way to push common config fleet-wide ([§4](#4-practical-consequences)) | – |
| `iscsi` | `config.json` of `iscsid`/`tgtd`; `configfs` persistence | `iscsid`: [NOT AVAILABLE] whether existing sessions are kernel-held and whether attach/detach during the window fails. `tgtd` (LVM backend with `tgtadm`, the default target helper on Debian/Ubuntu): [NOT AVAILABLE] whether tgtd keeps its targets across a restart, and so whether a `tgtd` restart cuts disk I/O for VMs using LVM volumes from that host ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)) | none | **storage path on computes** ([D §5.2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#52-iscsi-iscsid-tgtd)) | with care, per host batch | – |
| `baremetal` (`bootstrap-servers`) | `daemon.json`, `/etc/hosts`, packages, users | **yes** if `daemon.json` changes: the Docker restart (`state: restarted` unless `docker_systemd_reload`, default `false`, ansible-collection-kolla's `roles/docker/handlers/main.yml:10-15`, `roles/docker/defaults/main.yml:71`) stops every container, `nova_libvirt` and OVS included ([R14](risk-register.md#r14)) | yes on controllers | yes | no on a live host unless `daemon.json` is unchanged; use `--limit` | – |

Validation: `--list-tags` lists only the tags it can see statically (ansible-core 2.18.20
`lib/ansible/cli/playbook.py:201, :220-221`; [list-tags-site.txt](../reference/listings/list-tags-site.txt)); tags
that occur only inside dynamically included files, such as `service-rabbitmq` (reached through `include_role:
nova-cell, tasks_from: bootstrap`, `nova.yml:85-88`), do not appear. `--list-tasks` cannot show the tasks inside roles,
because they come from dynamic includes ([§2.6](#26---list-tasks-is-not-usable-for-kolla-code)). Use `genconfig` plus
`docker exec -u root <c> /usr/local/bin/kolla_set_configs --check` to predict restarts ([Predict and inspect a
run](../operations/predict-a-run.md); [Kolla images
§3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

---

## 4. Practical consequences

1. **Reconfiguring `common` is `-t common`.** `common` is its own play (`site.yml:88-103`) and no service play runs it
   [CODE] ([§2.1](#21-dynamic-include_tasks-and-tag-inheritance-code)). Changes to fluentd, cron or kolla_toolbox
   config reach a host only through:
   - `-t common`, on every host of the `common` group;
   - an untagged run.

   `-t chrony` does not exist (no chrony play), and `-t nova` or `-t neutron` do not touch the common containers.
   Changed in 2025.1: the common config step no longer ensures the fluentd image (2025.1
   `roles/common/tasks/config.yml` has no `ensure_image` task), so `-t common genconfig` pulls nothing.
2. **A service tag drags in shared infrastructure.**
   - `-t nova` also runs the loadbalancer play (nova frontends), Keystone registration and the DB bootstrap containers
     [CODE] (`site.yml:252-265`, `nova.yml:103-147`, `roles/nova/tasks/deploy.yml:2`, `nova.yml:29-100`). It does not
     run `common`: no role has a `meta/main.yml` dependency.
   - `-t neutron` also runs the neutron role on all computes.
   - A tag never restricts *which hosts* a play targets; use `--limit` for that.
3. **Changed in 2025.1: a service tag leaves frontend changes pending.** Because the loadbalancer play's check step
   carries only `haproxy`, `keepalived` and `loadbalancer` ([§2.2](#22-handlers-ignore-tags-code)), a change that
   alters a service's HAProxy frontend (a new port, a TLS setting, a new backend host) and is applied with `-t <svc>`
   needs a second run with `-t haproxy` (or `loadbalancer`), or an untagged run. Until then HAProxy serves the old
   frontend while the service runs with the new config [CODE]. That second run restarts HAProxy, hosts without the VIP
   first ([§5](#5-role--handler-map-core-services)).
4. **The impact is data-dependent.** The same command can be a no-op or a fleet-wide restart, depending on whether a
   rendered file, a container parameter or an image changed. That in turn depends on *global* variables (`enable_*`,
   group membership, passwords), not only on the tagged service [CODE]: e.g. common's cron logrotate config lists
   services by their `enable_*` flags (`roles/common/tasks/config.yml:171-240`). Since only the common play renders it,
   enabling a service with `-t <svc>` leaves the logrotate config stale until `-t common` or an untagged run, and that
   run then restarts `cron` through its check.
5. **`--skip-tags` can avoid the loadbalancer play.** `--skip-tags haproxy` skips the entire loadbalancer play,
   including the per-service includes ([fact sheet A §1.9][sheet-a-19]), because every task of the play inherits the
   play tags `haproxy`, `keepalived` and `loadbalancer` and one skipped tag is enough
   (ansible-core 2.18.20 `lib/ansible/playbook/taggable.py:79-90`), while leaving the service play untouched. Combining
   `-t nova` with `--skip-tags haproxy` is valid, and in 2025.1 it differs from `-t nova` alone only in not rewriting
   the frontend files, since `-t nova` restarts no HAProxy anyway. Some tags select no loadbalancer include at all:
   - `memcache` (only the memcached play);
   - nova's narrower play tags: `-t nova-bootstrap,nova-api-deploy,nova-cell-deploy,nova-refresh-scheduler-cell-cache`
     does what a `-t nova` deploy/reconfigure does, minus the loadbalancer includes (`site.yml:252-265`);
   - `common`, `openvswitch`, `ovn`, `iscsi`, `valkey` (their own plays only).

   `--skip-tags haproxy` does not skip the letsencrypt play, which carries only `letsencrypt` (`site.yml:329-341`).
6. **Tags do not change `kolla_action` logic, but the command decides batching.** For a given tag, `deploy` and
   `reconfigure` execute the same tasks (e.g. `-t nova deploy` and `-t nova reconfigure`; [Repository architecture
   §4.2](../concepts/repository-architecture.md#42-reconfigure-is-deploy)). Apart from bifrost, whose
   `reconfigure.yml` has its own logic, every role's `reconfigure.yml` imports or includes `deploy.yml` [CODE].
   Neutron's `bootstrap_neutron` container runs on deploy and reconfigure alike
   (`roles/neutron/tasks/bootstrap_service.yml:2-21`, no `when`; `roles/neutron/tasks/reconfigure.yml:2`). The other
   difference is `kolla_serial`: `reconfigure` always passes 0, `deploy` passes nothing, so only `deploy` honours your
   `-e kolla_serial=N` ([Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook)).

---

## 5. Role → handler map (core services)

Handlers run in **definition order** after `meta: flush_handlers` (end of `deploy.yml`) or at the end of the play
(ansible-core 2.18.20 `lib/ansible/executor/play_iterator.py:424-438`). All use `kolla_container`
`recreate_or_restart_container` unless noted. In 2025.1 each restart handler is notified by the shared check step for
its own container only ([§2.4](#24-loop-notify-is-gone-in-20251-code)). The complete list for all roles is in
[Generated inventory §3](../reference/generated-inventory.md#3-role-task-structure-handlers-and-helper-role-usage).

| Role | Handlers (definition order) | Special logic | Evidence |
|---|---|---|---|
| common | Restart fluentd → Restart kolla-toolbox (→ Initializing toolbox) → Restart cron | – | `roles/common/handlers/main.yml:2-50` |
| haproxy (role `loadbalancer`) | Check IP addresses on the API interface → Group HA nodes by status (VIP holder or not) → Stop backup keepalived / haproxy / proxysql → Start backup haproxy (→ wait) → Start backup proxysql (→ wait) → Start backup keepalived → Stop master haproxy / proxysql / keepalived → Start master haproxy (→ wait) → Start master proxysql (→ wait) → Start master keepalived → Wait for haproxy / proxysql to listen on the VIP → Restart haproxy-ssh | the stop/start handlers `listen` on `Restart haproxy container`, `Restart proxysql container` or `Restart keepalived container`; keepalived is stopped only when it is itself notified; stop/start, never reload; no flush in `deploy.yml`; **notified only by the play's final check step** (`site.yml:319-324`) | `roles/loadbalancer/handlers/main.yml:9-347`, `roles/loadbalancer/tasks/deploy.yml:2-11`, [A §1.5](../reference/factsheets/a-infra-lb-ovn.md#15-handlers-ansibleroleshaproxyhandlersmainyml-definition-order--run-order-see-common-mechanics) |
| mariadb | Bootstrap MariaDB cluster (listen: first container, port, WSREP, then `mariadb_bootstrap_restart` group) → Restart MariaDB on existing cluster members (`group_by: mariadb_restart`) → Start MariaDB on new nodes (`group_by: mariadb_start`) → Restart mariadb-clustercheck | the two `group_by` handlers now `listen` to `Restart mariadb container`, the name the shared check step notifies; the restart itself is in the `mariadb.yml` restart plays, `serial: "33%"`, waiting for port + WSREP `Synced` | `roles/mariadb/handlers/main.yml:2-90`, `mariadb.yml:18-52`, `roles/mariadb/tasks/restart_services.yml:2-53`, [B §1.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#15-handlers-ansiblerolesmariadbhandlersmainyml-in-definition-order) |
| rabbitmq | Restart rabbitmq container (`group_by: <project>_restart`) | the restart play drains the node (`rabbitmq_upgrade drain`), restarts it and waits with `rabbitmqctl wait`, `serial: "33%"` | `roles/rabbitmq/handlers/main.yml:2-4`, `rabbitmq.yml:30-49`, `roles/rabbitmq/tasks/restart_services.yml:10-49`, [B §2.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#25-handlers-ansiblerolesrabbitmqhandlersmainyml-in-definition-order) |
| etcd | Bootstrap etcd on new cluster → Look up the cluster leader → Bootstrap etcd on new services → Upgrade etcd non-leaders (upgrade only) → Rolling restart of etcd non-leaders (`% 4` loop) → Restart etcd leader → Remove deleted members | every handler is an `include_tasks` with `listen`; the restart itself is `roles/etcd/tasks/restart_services.yml` (restart, wait for the client port, `etcdctl endpoint health`) | `roles/etcd/handlers/main.yml:1-68`, `roles/etcd/tasks/restart_services.yml:2-41` |
| keystone | (Init keystone database upgrade, upgrade only) → Restart keystone-ssh → Restart keystone-fernet → Restart keystone → (Finish keystone database upgrade, upgrade only) | all hosts at once | `roles/keystone/handlers/main.yml:5-92`, [B §3.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#35-handlers-ansibleroleskeystonehandlersmainyml-order-is-load-bearing-comment-2-3) |
| nova | Restart nova-super-conductor → nova-scheduler → nova-api → nova-metadata (new) | skipped on upgrade when `nova_safety_upgrade` | `roles/nova/handlers/main.yml:2-68` |
| nova-cell | Restart nova-conductor → novncproxy → spicehtml5proxy → serialproxy → nova-ssh → **nova-libvirt** (retries 5; with `libvirt_enable_sasl`, default `true`, notifies the two next) → Checking libvirt container is ready → Create libvirt SASL user → Reload libvirtd (host service, notified from `external_ceph.yml`) → nova-compute → nova-compute-ironic → fake → Wait for nova-compute services (upgrade only) | libvirt is restarted **before** nova-compute when both changed | `roles/nova-cell/handlers/main.yml:2-216`, `roles/nova-cell/defaults/main.yml:578` |
| neutron | one handler per agent/server; L3 agent: stopped agents started first, then running agents in host-list order, each loop item preceded by a `neutron_l3_agent_failover_delay` pause (default `0`: no spacing, `roles/neutron/defaults/main.yml:626`) | L3 agent only | `roles/neutron/handlers/main.yml:82-135` |
| openvswitch | Restart openvswitch-db-server (→ Waiting for openvswitch_db) → Restart openvswitch-vswitchd | – | `roles/openvswitch/handlers/main.yml:2-40` |

## Related

- [Operations](../operations/index.md) (impact of each scenario, commands)
- [Risk register](risk-register.md) (risks [R1–R30](risk-register.md#r1))
- [Components](../components/index.md)
- [Tag index](tag-index.md) (tag index)
- [Ansible listings](../reference/listings/index.md) (ansible-core 2.18.20 `--list-tags` and `--list-tasks`)
- [Execution flow §7](../concepts/deployment-execution-flow.md#7-dependencies-introduced-by-handlers) (the loadbalancer
  restart step)

[sheet-a-19]: ../reference/factsheets/a-infra-lb-ovn.md#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy
[sheet-c-0]: ../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#0-cross-cutting-facts-apply-to-all-five-roles
