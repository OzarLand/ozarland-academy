---
title: Predict and inspect a run
description: In 2024.1, the commands that show what a kolla-ansible run would target, render and restart, from genconfig to kolla_set_configs --check and prechecks.
tags: [genconfig, kolla-set-configs, check-mode, prechecks, tags, podman]
remember:
  - "Predict a run with <code>genconfig</code>, then <code>kolla_set_configs --check</code> in each container; <code>--list-tasks</code> is not useful. <span class=\"ev ev-code\">CODE</span>"
  - "<code>genconfig</code> writes <code>/etc/kolla/&lt;svc&gt;/</code>, skips every container restart and re-renders haproxy <code>services.d</code> for the tagged services; new in 2024.1, an untagged or <code>-t common</code> <code>genconfig</code> pulls the fluentd image when it is absent. <span class=\"ev ev-code\">CODE</span>"
  - "With Docker, exit 1 (or 137) means drift; with Podman, only 1 does, and 137 fails the task. Any other code fails the check task instead of restarting. Keep <code>-u root</code>. <span class=\"ev ev-code\">CODE</span>"
  - "The check sees config files only: a changed image, volume or systemd unit text also restarts the container. On the first 2024.1 run, every unit still holding <code>StartLimitIntervalSec=</code> is drift, and every service that <code>kolla-ansible upgrade</code> has not reached gets its 2024.1 image. <span class=\"ev ev-code\">CODE</span>"
  - "Whether a <code>--check --diff</code> run fails or gives partial results is unknown, and the tasks marked <code>check_mode: false</code> (about 80) still run, two of which start one-shot containers: staging only. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
impact: [read-only, writes-config]
scenarios:
  - title: "The check returns 2"
    situation: "You changed a glance option and ran <code>kolla-ansible -i multinode -t glance genconfig</code>. On a controller, you run <code>docker exec glance_api /usr/local/bin/kolla_set_configs --check; echo $?</code> (without <code>-u root</code>) and it prints 2. Your colleague concludes that the check is broken and proposes to go ahead with the production <code>reconfigure</code>."
    ask: "What would you do?"
    choices:
      - text: "Read 2 as \"no drift\" and run the <code>reconfigure</code>."
        verdict: "avoid"
        why: "0 is the code for \"every listed file matches\". 2 = an unexpected exception, such as a <code>config.json</code> the user cannot open; when Kolla gets 2, the check task fails instead of restarting, if the comparison reaches the config check (it is skipped when the container is missing or its parameters already differ) <span class=\"ev ev-code\">CODE</span>."
      - text: "Re-run the same check with <code>docker exec -u root</code>, as Kolla does, and read the exit code then."
        verdict: "best"
        why: "Kolla runs the check as root, and containers that run as a service user cannot read the root-owned 0660 files in <code>/var/lib/kolla/config_files</code> <span class=\"ev ev-code\">CODE</span>. Then 0 = no config drift, 1 = drift, restart on the next run."
      - text: "Skip the check and preview the run with <code>EXTRA_OPTS=\"--check --diff\"</code> on production instead."
        verdict: "risky"
        why: "<code>kolla_container</code> does not declare check-mode support, so Ansible skips it under <code>--check</code>, while tasks marked <code>check_mode: false</code> still run, and two of them start one-shot containers (<code>nova_list_cells</code>, <code>nova_upgrade_checks</code>) <span class=\"ev ev-code\">CODE</span>. Whether such a run fails or gives partial results is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>: staging only."
    see: "1-commands-and-what-they-show"
  - title: "Every check returns 0 after the upgrade"
    situation: "Last week you upgraded from 2023.1 to 2024.1 with <code>-t nova,neutron,glance upgrade</code>. Today you plan a <code>reconfigure</code> without tags for a small keystone change. After <code>genconfig</code>, <code>docker exec -u root memcached /usr/local/bin/kolla_set_configs --check</code> and the same check in the other containers outside those three services print 0. Your colleague says only keystone will restart."
    ask: "What would you do?"
    choices:
      - text: "Trust the checks: 0 everywhere means only keystone restarts."
        verdict: "avoid"
        why: "<code>kolla_set_configs --check</code> compares only the files of <code>config.json</code>. <code>compare_container</code> also compares the image and the whole systemd unit text: the services outside the three upgraded ones still run 2023.1 images, and the 2024.1 template no longer writes <code>StartLimitIntervalSec=</code> <span class=\"ev ev-code\">CODE</span>."
      - text: "First run <code>kolla-ansible upgrade</code> for the services the partial upgrade left out; then list the units still written by 2023.1 with <code>grep -l StartLimitIntervalSec /etc/systemd/system/kolla-*-container.service</code>: each one will restart on the run, with the rest of its role on that host."
        verdict: "best"
        why: "An untagged <code>reconfigure</code> would move every service not yet upgraded to its 2024.1 image through the deploy path, without the role's upgrade tasks, since the image is compared too. A unit file that contains <code>StartLimitIntervalSec</code> cannot match the 2024.1 template, so the first 2024.1 check of that container reports drift and its handler restarts it; loop-notify adds the other containers of the role on that host <span class=\"ev ev-code\">CODE</span>."
      - text: "Run the <code>reconfigure</code> with <code>EXTRA_OPTS=\"--check\"</code> first to see the restarts."
        verdict: "risky"
        why: "<code>kolla_container</code>, which runs the comparison, is skipped under <code>--check</code>, so the restarts are not shown, and whether such a run is usable is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>."
    see: "2-the-first-20241-run-on-a-cloud-deployed-by-20231"
quiz:
  - q: "Is <code>--list-tasks</code> useful to predict a Kolla-Ansible run?"
    options: ["Yes, it lists every task that will run", "No: only <code>include_tasks</code> placeholders are shown"]
    answer: 1
    explain: "Row \"List tasks\" of the table: only <code>include_tasks</code> placeholders are shown, because the service roles are reached through dynamic includes."
    see: "1-commands-and-what-they-show"
  - q: "How can you see, on a host, whether a container's configuration will make it restart?"
    options: ["Run <code>kolla_set_configs --check</code> inside the container, as root, after <code>genconfig</code>", "Run <code>docker ps</code>"]
    answer: 0
    explain: "<code>docker exec -u root &lt;container&gt; /usr/local/bin/kolla_set_configs --check</code> (or <code>podman exec -u root</code>); the exit codes are in the table <span class=\"ev ev-code\">CODE</span>. It covers config files only, not image, volume or unit changes."
    see: "1-commands-and-what-they-show"
  - q: "In 2024.1, can an untagged <code>genconfig</code> download anything?"
    options: ["No: it only renders files", "Yes: the common config step pulls the fluentd image when it is not on the host"]
    answer: 1
    explain: "The common role's <code>config.yml</code> now runs <code>kolla_container</code> <code>ensure_image</code> on the fluentd image before reading its labels; <code>ensure_image</code> pulls when the image is absent <span class=\"ev ev-code\">CODE</span>."
    see: "1-commands-and-what-they-show"
  - q: "The checks run with <code>kolla_container_engine: podman</code>. What does Kolla do when <code>kolla_set_configs --check</code> exits 137?"
    options: ["It treats it as drift and restarts the container, as with Docker", "It fails the check task"]
    answer: 1
    explain: "The Podman worker treats only 1 as drift; any other non-zero code, 137 included, raises \"Failed to compare container configuration\" <span class=\"ev ev-code\">CODE</span>."
    see: "1-commands-and-what-they-show"
---

# Predict and inspect a run

The commands that show what a run would target, render and restart before it runs, read in Kolla-Ansible `2024.1-eom`.
Each row of the table gives one command, what it shows and its limits.
[§2](#2-the-first-20241-run-on-a-cloud-deployed-by-20231)
adds what the first 2024.1 run on a cloud deployed by 2023.1 restarts, and how to see it beforehand.

<img src="../assets/images/S3-predict-a-run.webp" width="1536" height="1024" loading="lazy" alt="LUMO holds a parchment beside a small brass server model on a workbench while Jo, carrying a crate, waits before touching anything.">

> [!NOTE]
> **Key answers**
>
> - **Predict a run:** `genconfig`, then `kolla_set_configs --check` in each container; the meaning of exit codes 0, 1,
>   2 and 137, with Docker and with Podman, is in the same table [CODE]. `--list-tasks` is not useful (table below).
> - **What the check does not show:** a container also restarts when its image, volumes or other parameters differ,
>   or when its systemd unit text differs [CODE]. After an upgrade from 2023.1, look at the unit files too, and at
>   the services the upgrade has not reached, whose image changes on the next run
>   ([§2](#2-the-first-20241-run-on-a-cloud-deployed-by-20231)).
> - **Changed in 2024.1:** `genconfig` can pull the fluentd image; the container module is `kolla_container`, with a
>   Podman path that reads the exit codes differently. `set_configs.py` itself is unchanged [CODE].

## 1. Commands and what they show

| Goal | Command | Notes |
|---|---|---|
| List tags as Ansible sees them | `EXTRA_OPTS="--list-tags" kolla-ansible -i multinode deploy` | Works. Shows the play tags and the tags inherited by the tasks of each play. `common` is tagged only on the common play (`site.yml:88-103`): no role has a `meta` dependency on it. [list-tags-site.txt](../reference/listings/list-tags-site.txt) is the ansible-core 2.16.20 parse of the 2024.1 tree, where `common` appears on play #5 only. Tags set inside dynamic includes, such as `rabbitmq-ha-precheck` (`roles/rabbitmq/tasks/precheck.yml:129`), are not listed ([Ansible listings](../reference/listings/index.md)) |
| List hosts a run would target | `EXTRA_OPTS="--list-hosts" kolla-ansible -i multinode -t nova reconfigure` | Plays with `&enable_<svc>_True` patterns show **0 hosts**: the groups are created at run time by `group_by` (`site.yml:6-74`; [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| List tasks | `EXTRA_OPTS="--list-tasks" …` | **Not useful**: only `include_tasks` placeholders are shown ([Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| Render configs without restarting | `kolla-ansible -i multinode genconfig [-t <svc>] [--limit <hosts>]` | Sets `kolla_action=config` (`tools/kolla-ansible:557-560`). Writes `/etc/kolla/<svc>/` on the targets. Every container restart handler is skipped (`when: kolla_action != "config"`, e.g. `roles/nova-cell/handlers/main.yml:89-90`). Also re-renders haproxy `services.d` (and, with the single external frontend, `external-frontend-map`) for the tagged services: the service includes of the loadbalancer play run for `config`, and each service's `loadbalancer.yml` imports `loadbalancer-config` with `tags: always` (`site.yml:324-326`; `roles/nova/tasks/loadbalancer.yml:2-7`; `roles/loadbalancer-config/tasks/main.yml:2-4`; `roles/haproxy-config/tasks/main.yml:2-23, :25-53`). Those tasks notify `Restart haproxy container`, but every loadbalancer handler is skipped under `config` (e.g. `roles/loadbalancer/handlers/main.yml:16-17`), so HAProxy keeps its old frontends. A later `-t <svc>` reconfigure then finds the file unchanged and does not restart HAProxy, and `-t <svc> deploy-containers` runs no loadbalancer work: the change reaches HAProxy only through `-t haproxy reconfigure` or an untagged run, whose loadbalancer check compares `services.d` (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:17`, `roles/loadbalancer/tasks/check-containers.yml:2-18`); that restart is staged, backups first and the VIP holder last (`roles/loadbalancer/handlers/main.yml:9-34`). To diff the frontends, copy `/etc/kolla/haproxy/services.d/` before `genconfig` ([Controlled batches §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). **New in 2024.1:** when the common play runs (no tag, or `-t common`), its config step runs `kolla_container` `ensure_image` on the fluentd image, then reads its labels (`roles/common/tasks/config.yml:42-91`; `enable_fluentd: "yes"`, `group_vars/all.yml:765`). `ensure_image` pulls the image when that tag is not on the host (`module_utils/kolla_docker_worker.py:501-503`, `module_utils/kolla_podman_worker.py:675-677`), so `genconfig` can need the registry, and fails on a host where the pull fails (`module_utils/kolla_docker_worker.py:189-223`). This is the only `kolla_container` task in a role's `config.yml` |
| See what will restart | on each host: `docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` (Podman: `podman exec -u root …`) | 0 = every file listed in `config.json`'s `config_files` matches its live copy (content, mode, owner). `command`, `permissions`, removed entries and optional entries whose source is absent are **not** compared, so memcached (`"config_files": []`) always returns 0. 1 = a listed file differs or is missing from the container, `optional` files included (a newly rendered `optional` file is drift) → restart on the next `deploy`/`reconfigure`/`deploy-containers`. 1 is also returned for a required source missing from `/var/lib/kolla/config_files` or an invalid `config.json`; the restarted container then fails `kolla_set_configs` at start. `preserve_properties` entries (no `perm`, so the mode check never matches) and directory sources with subdirectories return 1 on every run ([Kolla images §3.1](../concepts/kolla-images.md#31-what-is-compared)). 2 = an unexpected exception, such as a `config.json` that cannot be opened. kolla's `set_configs.py` is byte-identical to 2023.1's, so these codes still hold [CODE kolla `docker/base/set_configs.py:36-60, :64-72, :165-242, :245-298, :556-582`, kolla `docker/base/start.sh:3, :11`]. **What Kolla does with the code depends on the engine (changed in 2024.1):** with Docker, 0 = no drift, 1 and 137 = drift, a client error from the exec (container stopped or restarting) = drift, any other code fails the check task (`module_utils/kolla_docker_worker.py:146-181`, `library/kolla_container.py:410-429`); with Podman, a container that is not `running` is drift before any exec, a client error from the exec = drift, 0 = no drift, 1 = drift, and any other code, 137 included, fails the task (`module_utils/kolla_podman_worker.py:428-453`). The config check is reached only when the container exists and its parameters match: `compare_container` stops at the first difference (`module_utils/kolla_container_worker.py:58-65`), so a code that would fail the task does not when the image or parameters already differ. Details: [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes). Keep `-u root`: both workers run the check as root (`module_utils/kolla_docker_worker.py:146-152`, `module_utils/kolla_podman_worker.py:435-436`), and containers that run as a service user cannot read the root-owned 0660 files in `/var/lib/kolla/config_files` ([Kolla images §3.4](../concepts/kolla-images.md#34-running-it-by-hand-needs-root)) |
| See what else will restart | compare the image, volumes and other parameters of each container with the service definition; read `/etc/systemd/system/kolla-<container>-container.service` | The check task (`compare_container`) also reports drift when the container is missing, when one of 16 container parameters differs (image, volumes, environment, dimensions, healthcheck, …), or when the unit file on disk differs from the rendered template, whole text compared (`module_utils/kolla_container_worker.py:58-65, :67-89`; `module_utils/kolla_systemd_worker.py:20-39, :71, :84, :154-167`). `kolla_set_configs --check` sees none of these. A changed `docker_graceful_timeout`, `docker_client_timeout`, `docker_restart_policy` or `docker_restart_policy_retry` changes the unit text of every long-running container ([F16](../reference/findings.md#f16)) |
| Check-mode run | `EXTRA_OPTS="--check --diff" kolla-ansible … reconfigure` | [CODE] `kolla_container`, `kolla_container_facts` and `kolla_toolbox` do not declare check-mode support (`library/kolla_container.py:355-359`, `library/kolla_container_facts.py:120`, `library/kolla_toolbox.py:263`), so Ansible skips them under `--check` (ansible-core 2.16.20 `lib/ansible/module_utils/basic.py:506-507`) unless the task sets `check_mode: false`, and many tasks register outputs used later. About 80 tasks set `check_mode: false` and run for real even under `--check`: 42 of them are `kolla_container_facts` calls, mostly in the prechecks, and others run commands, such as the hacluster authkey generation (`roles/hacluster/tasks/bootstrap.yml:29-40`). Two are `kolla_container` tasks that start one-shot containers: `nova_list_cells` (`roles/nova-cell/tasks/get_cell_settings.yml:2-21`) and `nova_upgrade_checks` (`roles/nova/tasks/upgrade.yml:9-30`). A third, `rabbitmq_version_check` (`roles/rabbitmq/tasks/version-check.yml:18-36`), also sets it but is not reached under `--check`: its block runs only when the preceding `kolla_container_facts` task found a `rabbitmq` container, and that task is skipped (`roles/rabbitmq/tasks/version-check.yml:3-9, :75`). [NOT AVAILABLE] Whether such a run fails or gives partial results, and which of those tasks it reaches; staging only |
| Pre-deployment checks | `kolla-ansible -i multinode prechecks [-t <svc>]` | Sets `kolla_action=precheck` (`tools/kolla-ansible:444-447`). Read-only ([fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md)), apart from the commands it runs inside existing containers, e.g. `rabbitmqctl list_queues` (`roles/rabbitmq/tasks/precheck.yml:131-137`). `-t <svc>` skips the `prechecks` role (untagged play, `site.yml:77-86`) but runs `<svc>/precheck.yml`. **Changed in 2024.1:** the `prechecks` role fails when `om_enable_rabbitmq_high_availability` and `om_enable_rabbitmq_quorum_queues` are equal (`roles/prechecks/tasks/service_checks.yml:67-72`), and the rabbitmq precheck asserts that the existing queues are quorum queues when quorum is on, the new default ([F17](../reference/findings.md#f17)); the Docker version check runs only with Docker (`roles/prechecks/tasks/service_checks.yml:9-19`) |

## 2. The first 2024.1 run on a cloud deployed by 2023.1

The first `deploy`, `reconfigure` or `deploy-containers` that the 2024.1 code runs on a host can restart containers
whose operator config did not change. Three causes come from the code, and each can be seen before the run [CODE].
A fourth applies to every service that `kolla-ansible upgrade` has not reached yet, below the table:

| Cause | Containers | How to see it before the run |
|---|---|---|
| **Unit text** ([F16](../reference/findings.md#f16)). The 2024.1 template writes `StartLimitInterval=` where 2023.1 wrote `StartLimitIntervalSec=` and a blank line; it names the engine in `Description`, `After`/`Wants`, `ExecStart` and `ExecStop`, which with Docker read as in 2023.1, so the start-limit line is what differs (`module_utils/kolla_systemd_worker.py:20-39, :50-54`); `check_unit_change` compares the whole file (`:154-167`). A container that the 2024.1 code has not yet created or restarted still has the unit that 2023.1 wrote | every long-running container not recreated or restarted by 2024.1 code whose role runs a check task, for example one outside the tags of a partial upgrade; Swift `deploy` uses `start_container`, which does not compare the unit (`roles/swift/tasks/deploy.yml:1-10`). A container recreated or restarted by the upgrade got the new unit then | `grep -l StartLimitIntervalSec /etc/systemd/system/kolla-*-container.service`: the 2024.1 template has no such key (`module_utils/kolla_systemd_worker.py:27`), so each file listed differs from it and its container reports drift. `kolla_set_configs --check` does not show it |
| **`hostnqn` file** (new in 2024.1). nova-cell and cinder render `nqn.2014-08.org.nvmexpress:uuid:<hostname uuid>` into `hostnqn` and notify the restart (`roles/nova-cell/tasks/config.yml:203-216`, `roles/cinder/tasks/config.yml:95-108`); the `config.json` of both copies it, not optional, to `/etc/nvme/hostnqn` (`roles/nova-cell/templates/nova-compute.json.j2:59-63`, `roles/cinder/templates/cinder-volume.json.j2:23-27`) | `nova_compute` and `cinder_volume`, and by loop-notify the other containers of the same role on that host ([Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)) | after `genconfig`, `kolla_set_configs --check` in `nova_compute` and `cinder_volume` exits 1: the destination `/etc/nvme/hostnqn` is missing or differs from the rendered file in content, mode (0644) or owner (root) (kolla `docker/base/set_configs.py:165-197`); the images install `nvme-cli`, so whether the file already exists in the container is [NOT AVAILABLE] |
| **Quorum queues** ([F17](../reference/findings.md#f17)). `om_enable_rabbitmq_quorum_queues` now defaults to `true` (`group_vars/all.yml:266-268`), rendered as `rabbit_quorum_queue = true` in the `[oslo_messaging_rabbit]` section of the service configs (e.g. `roles/nova-cell/templates/nova.conf.j2:207-216`) | every service whose config renders that section, if the 2023.1 default was kept | after `genconfig`, a diff of `/etc/kolla/<service>/` shows the new line and the check exits 1. `kolla-ansible prechecks` fails first while classic queues exist (`roles/rabbitmq/tasks/precheck.yml:131-152, :185-189`) |

**Image tag.** `openstack_release` defaults to `2024.1` (`group_vars/all.yml:679-681`) and every image tag follows it
(e.g. `roles/keystone/defaults/main.yml:96-100`). The check task compares the image
(`module_utils/kolla_container_worker.py:75`), and the restart handler recreates a container whose image differs,
pulling it first when absent (`module_utils/kolla_docker_worker.py:353-361`). So a `deploy`, `reconfigure` or
`deploy-containers` moves every service that `kolla-ansible upgrade` has not reached (the whole cloud before the
upgrade, the services outside the tags after `upgrade -t <svc>`) to its 2024.1 image through the deploy path, without
the role's upgrade tasks (e.g. `roles/keystone/tasks/upgrade.yml:23-31`). `kolla_set_configs --check` does not show it;
compare the image tag of each running container (`docker ps`) with the 2024.1 tag. Run `kolla-ansible upgrade` for those
services first.

A container recreated or restarted by 2024.1 code gets the new unit (`module_utils/kolla_systemd_worker.py:172-185`,
called on create and restart, `module_utils/kolla_docker_worker.py:334-339, :439-459`), so the unit cause appears once.
[NOT AVAILABLE] What these restarts do to the running VMs and to existing classic queues: the sources do not
establish it. The checklist for that run is in [Pre-execution
checklist §2](pre-execution-checklist.md#2-first-20241-run-on-a-cloud-deployed-by-20231).

## Related

- [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) — what
  `kolla_set_configs --check` compares, what it never compares, and its exit codes with Docker and Podman
- [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code) — why `--list-tasks` shows only
  placeholders and why some plays list 0 hosts
- [Pre-execution checklist](pre-execution-checklist.md) — step 1 uses `genconfig` and the check before a production run
- [Write config first, apply in controlled batches](controlled-batches.md) — applying what `genconfig` wrote, batch by
  batch
- [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) — the rows
  `genconfig` and `precheck` of the action matrix
- [Apply `common` changes](apply-common-changes.md) — the fluentd `ensure_image` step that `genconfig` now runs
- [Technical findings F14, F16, F17](../reference/findings.md#f14) — the blind spots of the check, the unit-text
  drift and the quorum-queue default
- [Fact sheet E
  §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks) —
  what `prechecks` checks
- [Open questions Q9](../troubleshooting/open-questions.md#q9) — check mode (`--check --diff`) usability:
  [NOT AVAILABLE]
