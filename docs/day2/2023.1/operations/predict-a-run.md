---
title: Predict and inspect a run
description: The commands that show what a kolla-ansible run would target, render and restart, from the Ansible listings to kolla_set_configs --check and prechecks.
tags: [genconfig, kolla-set-configs, check-mode, prechecks, tags]
remember:
  - "Predict a run with <code>genconfig</code>, then <code>kolla_set_configs --check</code> in each container; <code>--list-tasks</code> is not useful. <span class=\"ev ev-code\">CODE</span>"
  - "<code>genconfig</code> writes <code>/etc/kolla/&lt;svc&gt;/</code> on the targets and skips every container restart handler, but also re-renders haproxy <code>services.d</code> for the tagged services, so a later <code>-t &lt;svc&gt;</code> run no longer restarts HAProxy for that change."
  - "Exit 1 (or 137) means drift: a restart on the next <code>deploy</code>/<code>reconfigure</code>/<code>deploy-containers</code>; on 2 or any other code, <code>kolla_docker</code> fails the check task instead of restarting. <span class=\"ev ev-code\">CODE</span>"
  - "Keep <code>-u root</code> on the check: containers that run as a service user cannot read the root-owned files in <code>/var/lib/kolla/config_files</code>."
  - "Whether a <code>--check --diff</code> run fails or gives partial results is unknown: staging only. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
impact: [read-only, writes-config]
scenarios:
  - title: "The check returns 2"
    situation: "You changed a glance option and ran <code>kolla-ansible -i multinode -t glance genconfig</code>. On a controller, you run <code>docker exec glance_api /usr/local/bin/kolla_set_configs --check; echo $?</code> (without <code>-u root</code>) and it prints 2. Your colleague concludes that the check is broken and proposes to go ahead with the production <code>reconfigure</code>."
    ask: "What would you do?"
    choices:
      - text: "Read 2 as \"no drift\" and run the <code>reconfigure</code>."
        verdict: "avoid"
        why: "0 is the code for \"every listed file matches\". 2 = an unexpected exception; on 2, <code>kolla_docker</code> fails the check task instead of restarting <span class=\"ev ev-code\">CODE</span>."
      - text: "Re-run the same check with <code>docker exec -u root</code>, as Kolla does, and read the exit code then."
        verdict: "best"
        why: "Keep <code>-u root</code>: Kolla runs the check as root, and containers that run as a service user cannot read the root-owned 0660 files in <code>/var/lib/kolla/config_files</code>. Then 0 = no drift, 1 (or 137) = drift, restart on the next run."
      - text: "Skip the check and preview the run with <code>EXTRA_OPTS=\"--check --diff\"</code> on production instead."
        verdict: "risky"
        why: "<code>kolla_docker</code> does not declare check-mode support, so Ansible skips it under <code>--check</code>, and many tasks register outputs used later <span class=\"ev ev-code\">CODE</span>. Whether such a run fails or gives partial results is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>: staging only."
quiz:
  - q: "Is <code>--list-tasks</code> useful to predict a Kolla-Ansible run?"
    options: ["Yes, it lists every task that will run", "No: only <code>include_tasks</code> placeholders are shown"]
    answer: 1
    explain: "Row \"List tasks\" of the table: only <code>include_tasks</code> placeholders are shown."
  - q: "How can you see, on a host, whether a container will be restarted?"
    options: ["Run <code>kolla_set_configs --check</code> inside the container, as root", "Run <code>docker ps</code>"]
    answer: 0
    explain: "After <code>genconfig</code>, <code>docker exec -u root &lt;container&gt; /usr/local/bin/kolla_set_configs --check</code>; the meaning of exit codes 0, 1, 2 and 137 is in the table <span class=\"ev ev-code\">CODE</span>."
---

# Predict and inspect a run

The commands that show what a run would target, render and restart before it runs. Each row of the table gives one
command, what it shows and its limits.

> [!NOTE]
> **Key answers**
>
> - **Predict a run:** `genconfig`, then `kolla_set_configs --check` in each container; the meaning of exit codes 0, 1,
>   2 and 137 is in the same table [CODE]. `--list-tasks` is not useful (table below).

| Goal | Command | Notes |
|---|---|---|
| List tags as Ansible sees them | `EXTRA_OPTS="--list-tags" kolla-ansible -i multinode deploy` | Works. Shows the inherited task tags. `common` is no longer inherited by every role: 2023.1 roles have no `meta` dependencies and the common play is tagged `common` only (`site.yml:86-97`). The linked [list-tags-site.txt](../reference/listings/list-tags-site.txt) is the Ussuri parse, where `common` appears nearly everywhere |
| List hosts a run would target | `EXTRA_OPTS="--list-hosts" kolla-ansible -i multinode -t nova reconfigure` | Plays with `&enable_<svc>_True` patterns show **0 hosts**: the groups are created at run time ([Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| List tasks | `EXTRA_OPTS="--list-tasks" …` | **Not useful**: only `include_tasks` placeholders are shown ([Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| Render configs without restarting | `kolla-ansible -i multinode genconfig [-t <svc>] [--limit <hosts>]` | Writes `/etc/kolla/<svc>/` on the targets. Every container restart handler is skipped (`when: kolla_action != "config"`). Also re-renders haproxy `services.d` for the tagged services: the service includes of the `loadbalancer` play run for `config` and each service's `loadbalancer.yml` imports `loadbalancer-config` with `tags: always` (`tools/kolla-ansible:540-542`; `site.yml:339-341`; `roles/nova/tasks/loadbalancer.yml:2-7`; `roles/loadbalancer-config/tasks/main.yml:2-4`; `roles/haproxy-config/tasks/main.yml:14`). The loadbalancer handlers are skipped too (`roles/loadbalancer/handlers/main.yml:17`), so a later `-t <svc>` run finds that file unchanged and does not restart HAProxy: copy `services.d` before `genconfig` to diff it, and apply a frontend change with `-t haproxy reconfigure` or a run without tags |
| See what will restart | on each host: `docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` | 0 = every file listed in `config.json`'s `config_files` matches its live copy (content, mode, owner). `command`, `permissions`, removed entries and optional entries whose source is absent are **not** compared, so memcached (`"config_files": []`) always returns 0. 1 = a listed file differs or is missing from the container, `optional` files included (a newly rendered `optional` file such as nova-compute `release` is drift, exit 1; in Ussuri it gave 2) → restart on the next `deploy`/`reconfigure`/`deploy-containers`. 1 is also returned for a required source missing from `/var/lib/kolla/config_files` or an invalid `config.json`; the restarted container then fails `kolla_set_configs` at start. `preserve_properties` entries (no `perm`, so the mode check never matches) and, in practice, directory sources with subdirectories return 1 on every run ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)). 137 is also treated as drift. 2 = an unexpected exception, such as a missing `config.json`. On 2, or any code other than 0, 1 and 137, `kolla_docker` fails the check task instead of restarting [CODE `module_utils/kolla_docker_worker.py:155-190`, `library/kolla_docker.py:399-412`, kolla `docker/base/set_configs.py:36-60, :64-72, :165-242, :245-298, :556-582`, kolla `docker/base/start.sh:3, :11`]. Details: [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes). Keep `-u root`: Kolla runs the check as root (`module_utils/kolla_docker_worker.py:155-162`), and containers that run as a service user cannot read the root-owned 0660 files in `/var/lib/kolla/config_files` |
| Check-mode run | `EXTRA_OPTS="--check --diff" kolla-ansible … reconfigure` | [CODE] `kolla_docker` does not declare check-mode support (`library/kolla_docker.py:345-349`), so Ansible skips it under `--check` (ansible-core 2.14.18 `lib/ansible/module_utils/basic.py:520-521`). Many tasks register outputs used later. [NOT AVAILABLE] Whether such a run fails or gives partial results; staging only |
| Pre-deployment checks | `kolla-ansible -i multinode prechecks [-t <svc>]` | Read-only ([fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md)). `-t <svc>` skips the `prechecks` role (untagged play, `site.yml:79-84`) but runs `<svc>/precheck.yml` |

## Related

- [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) — what
  `kolla_set_configs --check` compares, what it never compares, and its exit codes
- [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code) — why `--list-tasks` shows only
  placeholders and why some plays list 0 hosts
- [Pre-execution checklist](pre-execution-checklist.md) — step 1 uses `genconfig` and the check before a production run
- [Write config first, apply in controlled batches](controlled-batches.md) — applying what `genconfig` wrote, batch by
  batch
- [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) — the rows
  `genconfig` and `precheck` of the action matrix
- [Fact sheet E
  §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks) —
  what `prechecks` checks
- [Open questions Q9](../troubleshooting/open-questions.md#q9) — check mode (`--check --diff`) usability:
  [NOT AVAILABLE]
