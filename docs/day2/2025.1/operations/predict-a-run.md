---
title: Predict and inspect a run
description: In 2025.1, the commands that show what a kolla-ansible run would target, render and restart, from genconfig to kolla_set_configs --check and prechecks.
tags: [genconfig, kolla-set-configs, check-mode, prechecks, tags, podman]
remember:
  - "Predict a run with <code>genconfig</code>, then <code>kolla_set_configs --check</code> in each container; <code>--list-tasks</code> is not useful. <span class=\"ev ev-code\">CODE</span>"
  - "<code>genconfig</code> writes <code>/etc/kolla/&lt;svc&gt;/</code> and the haproxy <code>services.d</code> files of the tagged services, and restarts nothing apart from two narrow cases; changed in 2025.1, it no longer pulls the fluentd image. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: the check also compares the container's command with <code>config.json</code>, and flags a recorded file that <code>config.json</code> no longer lists. With Docker, exit 1 (or 137) means drift; with Podman, only 1 does. Keep <code>-u root</code>. <span class=\"ev ev-code\">CODE</span>"
  - "The check sees config files and the command only: a changed image, volume, dimension or systemd unit text also restarts the container. On the first 2025.1 run after an upgrade from 2024.1, every unit without <code>PartOf=kolla.target</code> is drift, and with Docker outside the Red Hat family the new default ulimits recreate most containers. <span class=\"ev ev-code\">CODE</span>"
  - "Whether a <code>--check --diff</code> run fails or gives partial results is unknown, and the tasks marked <code>check_mode: false</code> (86) still run, five of which start one-shot containers: staging only. <span class=\"ev ev-na\">NOT AVAILABLE</span>"
impact: [read-only, writes-config]
scenarios:
  - title: "The check returns 2"
    situation: "You changed a glance option and ran <code>kolla-ansible genconfig -i multinode -t glance</code>. On a controller, you run <code>docker exec glance_api /usr/local/bin/kolla_set_configs --check; echo $?</code> (without <code>-u root</code>) and it prints 2. Your colleague concludes that the check is broken and proposes to go ahead with the production <code>reconfigure</code>."
    ask: "What would you do?"
    choices:
      - text: "Read 2 as \"no drift\" and run the <code>reconfigure</code>."
        verdict: "avoid"
        why: "0 is the code for \"no drift\". 2 = an unexpected exception, such as a <code>config.json</code> the user cannot open; when Kolla gets 2, the check task fails instead of restarting, if the comparison reaches the config check (it is skipped when the container is missing or its parameters already differ) <span class=\"ev ev-code\">CODE</span>."
      - text: "Re-run the same check with <code>docker exec -u root</code>, as Kolla does, and read the exit code then."
        verdict: "best"
        why: "Kolla runs the check as root, and containers that run as a service user cannot read the root-owned 0660 files in <code>/var/lib/kolla/config_files</code> <span class=\"ev ev-code\">CODE</span>. Then 0 = no config drift, 1 = drift, restart on the next run."
      - text: "Skip the check and preview the run with <code>--check --diff</code> on production instead."
        verdict: "risky"
        why: "<code>kolla_container</code> does not declare check-mode support, so Ansible skips it under <code>--check</code>, while tasks marked <code>check_mode: false</code> still run, and five of them start one-shot containers (<code>nova_list_cells</code>, <code>nova_upgrade_checks</code>, the two libvirt image checks, <code>rabbitmq_version_check</code>) <span class=\"ev ev-code\">CODE</span>. Whether such a run fails or gives partial results is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>: staging only."
    see: "1-commands-and-what-they-show"
  - title: "Every check returns 0 after the upgrade"
    situation: "Last week you upgraded from 2024.1 to 2025.1 with <code>kolla-ansible upgrade -t nova,neutron,glance</code>. Today you plan a <code>reconfigure</code> without tags for a small keystone change, on Ubuntu hosts with Docker. After <code>genconfig</code>, <code>docker exec -u root memcached /usr/local/bin/kolla_set_configs --check</code> and the same check in the other containers outside those three services print 0. Your colleague says only keystone will restart."
    ask: "What would you do?"
    choices:
      - text: "Trust the checks: 0 everywhere means only keystone restarts."
        verdict: "avoid"
        why: "<code>kolla_set_configs --check</code> compares only the command and the files of <code>config.json</code>. <code>compare_container</code> also compares the image, the dimensions and the whole systemd unit text: the services outside the three upgraded ones still run 2024.1 images, their units lack <code>PartOf=kolla.target</code>, and with Docker on Ubuntu the new default ulimits differ too <span class=\"ev ev-code\">CODE</span>."
      - text: "First run <code>kolla-ansible upgrade</code> for the services the partial upgrade left out; then list the units still written by 2024.1 with <code>grep -L PartOf=kolla.target /etc/systemd/system/kolla-*-container.service</code>: each one will restart on the run."
        verdict: "best"
        why: "An untagged <code>reconfigure</code> would move every service not yet upgraded to its 2025.1 image through the deploy path, without the role's upgrade tasks, since the image is compared too. A unit file without <code>PartOf=kolla.target</code> cannot match the 2025.1 template, so the first 2025.1 check of that container reports drift and its handler restarts it <span class=\"ev ev-code\">CODE</span>. The run also goes to every host at once: <code>reconfigure</code> always uses <code>kolla_serial=0</code>."
      - text: "Run the <code>reconfigure</code> with <code>--check</code> first to see the restarts."
        verdict: "risky"
        why: "<code>kolla_container</code>, which runs the comparison, is skipped under <code>--check</code>, so the restarts are not shown, and whether such a run is usable is not known <span class=\"ev ev-na\">NOT AVAILABLE</span>."
    see: "2-the-first-20251-run-on-a-cloud-deployed-by-20241"
quiz:
  - q: "Is <code>--list-tasks</code> useful to predict a Kolla-Ansible run?"
    options: ["Yes, it lists every task that will run", "No: only <code>include_tasks</code> placeholders are shown"]
    answer: 1
    explain: "Row \"List tasks\" of the table: only <code>include_tasks</code> placeholders are shown, because the service roles are reached through dynamic includes."
    see: "1-commands-and-what-they-show"
  - q: "How can you see, on a host, whether a container's configuration will make it restart?"
    options: ["Run <code>kolla_set_configs --check</code> inside the container, as root, after <code>genconfig</code>", "Run <code>docker ps</code>"]
    answer: 0
    explain: "<code>docker exec -u root &lt;container&gt; /usr/local/bin/kolla_set_configs --check</code> (or <code>podman exec -u root</code>); the exit codes are in the table <span class=\"ev ev-code\">CODE</span>. It covers the command and the config files only, not image, volume, dimension or unit changes."
    see: "1-commands-and-what-they-show"
  - q: "In 2025.1, does a memcached setting change show in <code>kolla_set_configs --check</code>?"
    options: ["No: memcached lists no config files, so the check always returns 0", "Yes: the setting is in the command of <code>config.json</code>, which the check now compares"]
    answer: 1
    explain: "New in 2025.1, the check compares the <code>command</code> of <code>config.json</code> with <code>/run_command</code>, written at the last start; a changed command exits 1 <span class=\"ev ev-code\">CODE</span>."
    see: "1-commands-and-what-they-show"
  - q: "The checks run with <code>kolla_container_engine: podman</code>. What does Kolla do when <code>kolla_set_configs --check</code> exits 137?"
    options: ["It treats it as drift and restarts the container, as with Docker", "It fails the check task"]
    answer: 1
    explain: "The Podman worker treats only 1 as drift; any other non-zero code, 137 included, raises \"Failed to compare container configuration\" <span class=\"ev ev-code\">CODE</span>."
    see: "1-commands-and-what-they-show"
---

# Predict and inspect a run

The commands that show what a run would target, render and restart before it runs, read in Kolla-Ansible `2025.1-eom`.
Each row of the table gives one command, what it shows and its limits.
[§2](#2-the-first-20251-run-on-a-cloud-deployed-by-20241) adds what the first 2025.1 run on a cloud deployed by 2024.1
restarts, and how to see it beforehand.

> [!NOTE]
> **Key answers**
>
> - **Predict a run:** `genconfig`, then `kolla_set_configs --check` in each container; the meaning of exit codes 0, 1,
>   2 and 137, with Docker and with Podman, is in the same table [CODE]. `--list-tasks` is not useful (table below).
> - **Changed in 2025.1, the check sees more:** it also compares the container's command with `config.json`, and
>   flags a file that an earlier start recorded and that `config.json` no longer lists [CODE].
> - **What the check does not show:** a container also restarts when its image, volumes, dimensions or other
>   parameters differ, or when its systemd unit text differs [CODE]. After an upgrade from 2024.1, look at the unit
>   files, at the ulimits on Docker hosts outside the Red Hat family, and at the services the upgrade has not reached,
>   whose image changes on the next run ([§2](#2-the-first-20251-run-on-a-cloud-deployed-by-20241)).
> - **Changed in 2025.1, `genconfig`:** it no longer pulls the fluentd image, and apart from two narrow cases no config
>   task notifies a restart any more [CODE]. The CLI options follow the sub-command (`kolla-ansible genconfig -i
>   multinode -t glance`).

## 1. Commands and what they show

| Goal | Command | Notes |
|---|---|---|
| List tags as Ansible sees them | `ansible-playbook -i multinode --list-tags <share>/kolla-ansible/ansible/site.yml` | **Changed in 2025.1:** the CLI has no way to pass `--list-tags` or `--list-hosts` (the `EXTRA_OPTS` environment variable of 2024.1 is gone; [Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook)), so run `ansible-playbook` on the installed playbook directly; `<share>` is the data directory of the installed package. Shows the play tags and the tags inherited by the tasks of each play. `common` is tagged only on the common play (`site.yml:88-103`): no role has a `meta` dependency on it. [list-tags-site.txt](../reference/listings/list-tags-site.txt) is the ansible-core 2.18.20 parse of the 2025.1 tree, where `common` appears on play #5 only. Tags set inside dynamic includes, such as `rabbitmq-ha-precheck` (`roles/rabbitmq/tasks/precheck.yml:164`), are not listed ([Ansible listings](../reference/listings/index.md)) |
| List hosts a run would target | `ansible-playbook -i multinode -t nova --list-hosts <share>/kolla-ansible/ansible/site.yml` | Not available through the CLI (row above). Plays with `&enable_<svc>_True` patterns show **0 hosts**: the groups are created at run time by `group_by` (`site.yml:6-74`; [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| List tasks | `kolla-ansible deploy -i multinode --list-tasks` | The one listing option the CLI kept (`kolla_ansible/ansible.py:88-94, :240-241`). **Not useful**: only `include_tasks` placeholders are shown ([Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code)) |
| Render configs without restarting | `kolla-ansible genconfig -i multinode [-t <svc>] [--limit <hosts>]` | Sets `kolla_action=config` (`kolla_ansible/cli/commands.py:113-125`). Writes `/etc/kolla/<svc>/` on the targets. **Changed in 2025.1:** the config tasks no longer notify the restart handlers, apart from two that still can, for `placement-api` with `placement_wsgi_provider: apache` and for `cinder-volume` with Huawei XML files ([Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does)); restarts come from the shared check step, which `genconfig` does not run. Also re-renders haproxy `services.d` (and, with the single external frontend, `external-frontend-map`) for the tagged services: the service includes of the loadbalancer play run for `config` (`site.yml:325-327`), and the loadbalancer's own `check-containers` step is skipped under `config` (`site.yml:319-324`), so HAProxy keeps its old frontends. A later `-t <svc>` reconfigure does not apply them either: in 2025.1 only `-t haproxy` (or `keepalived`, `loadbalancer`) or an untagged run reaches that check step, whose comparison covers `services.d` (`roles/loadbalancer/templates/haproxy/haproxy.json.j2:17-18`, `roles/loadbalancer/tasks/check-containers.yml:2-3`); that restart is staged, backups first and the VIP holder last (`roles/loadbalancer/handlers/main.yml:9-34`) ([Tags §2.2](../risk/tags.md#22-handlers-ignore-tags-code)). To diff the frontends, copy `/etc/kolla/haproxy/services.d/` before `genconfig` ([Controlled batches §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). **Changed in 2025.1:** the fluentd `ensure_image` of 2024.1 is gone (`roles/common/tasks/config.yml` has no `kolla_container` task), so `genconfig` no longer needs the registry |
| See what will restart | on each host: `docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` (Podman: `podman exec -u root …`) | 0 = the command matches, no recorded file was dropped and every file listed in `config.json`'s `config_files` matches its live copy (content, mode, owner). **New in 2025.1:** 1 when the `command` of `config.json` differs from `/run_command`, written at the last start, so a memcached setting change now shows; and 1 when a destination recorded in the container's defaults state is no longer listed in `config.json`, which repeats on every run until the container is recreated. `permissions`, unrecorded removed entries and optional entries whose source is absent are still **not** compared. 1 = also a listed file that differs or is missing from the container, `optional` files included (a newly rendered `optional` file is drift) → restart on the next `deploy`/`reconfigure`/`deploy-containers`. 1 is also returned for a required source missing from `/var/lib/kolla/config_files` or an invalid `config.json`; the restarted container then fails `kolla_set_configs` at start. `preserve_properties` entries (no `perm`, so the mode check never matches) and directory sources with subdirectories return 1 on every run. 2 = an unexpected exception, such as a `config.json` that cannot be opened or a missing `/run_command` (kolla `docker/base/set_configs.py:580-586, :589-642, :645-666`; [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)) [CODE]. **What Kolla does with the code depends on the engine:** with Docker, 0 = no drift, 1 and 137 = drift, a client error from the exec (container stopped or restarting) = drift, any other code fails the check task (`module_utils/kolla_docker_worker.py:146-181`, `library/kolla_container.py:423-425`); with Podman, a container that is not `running` is drift before any exec, a client error from the exec = drift, 0 = no drift, 1 = drift, and any other code, 137 included, fails the task (`module_utils/kolla_podman_worker.py:524-552`). The config check is reached only when the container exists and its parameters match: `compare_container` stops at the first difference (`module_utils/kolla_container_worker.py:58-65`), so a code that would fail the task does not when the image or parameters already differ. Keep `-u root`: both workers run the check as root (`module_utils/kolla_docker_worker.py:148-152`, `module_utils/kolla_podman_worker.py:531-532`), and containers that run as a service user cannot read the root-owned 0660 files in `/var/lib/kolla/config_files` ([Kolla images §3.4](../concepts/kolla-images.md#34-running-it-by-hand-needs-root)). The check runs the `set_configs.py` of the image the container runs: a container still on a 2024.1 image runs the 2024.1 check, without the command and state checks |
| See what else will restart | compare the image, volumes, dimensions and other parameters of each container with the service definition; read `/etc/systemd/system/kolla-<container>-container.service` | The check task (`compare_container`) also reports drift when the container is missing, when one of its compared parameters differs (image, volumes, environment, dimensions, healthcheck, …), or when the unit file on disk differs from the rendered template, whole text compared (`module_utils/kolla_container_worker.py:58-89`; `module_utils/kolla_systemd_worker.py:20-40, :155-168`). `kolla_set_configs --check` sees none of these. A changed `docker_graceful_timeout`, `docker_client_timeout`, `docker_restart_policy` or `docker_restart_policy_retry` changes the unit text of every long-running container ([F16](../reference/findings.md#f16)) |
| Check-mode run | `kolla-ansible reconfigure -i multinode --check --diff` | [CODE] `kolla_container` and `kolla_container_facts` do not declare check-mode support (no `supports_check_mode` in `library/kolla_container.py:351-355` or in `library/kolla_container_facts.py`), so Ansible skips them under `--check` (ansible-core 2.18.20 `lib/ansible/module_utils/basic.py:447-448`) unless the task sets `check_mode: false`, and many tasks register outputs used later. **Changed in 2025.1:** `kolla_toolbox` now declares check-mode support and passes `--check` to the `ansible` command it runs inside the `kolla_toolbox` container (`library/kolla_toolbox.py:148-149, :273-274`); what the inner modules (MySQL, RabbitMQ, OpenStack) then report is [NOT AVAILABLE]. 86 tasks set `check_mode: false` (or `no`) and run for real even under `--check` (a YAML walk of `roles/*/tasks`, `roles/*/handlers` and the playbooks): 46 are `kolla_container_facts` calls, 18 `command` tasks (for example the RabbitMQ queue listing of the precheck, `roles/rabbitmq/tasks/precheck.yml:110-116`, and the hacluster authkey generation, `roles/hacluster/tasks/bootstrap.yml:28-42`), 7 `kolla_toolbox` calls and 5 `kolla_container` tasks that start one-shot containers: `nova_list_cells` (`roles/nova-cell/tasks/get_cell_settings.yml:2-21`), `nova_upgrade_checks` (`roles/nova/tasks/upgrade.yml:5-26`), `libvirt_version_check` and `nova_libvirt_script_check` (`roles/nova-cell/tasks/version-check.yml:3-21, :80-98`) and `rabbitmq_version_check` (`roles/rabbitmq/tasks/version-check.yml:19-37`). The last is not reached under `--check`: its block runs only when the preceding `kolla_container_facts` task found a `rabbitmq` container, and that task is skipped (`roles/rabbitmq/tasks/version-check.yml:3-9, :76`). [NOT AVAILABLE] Whether such a run fails or gives partial results, and which of those tasks it reaches; staging only |
| Pre-deployment checks | `kolla-ansible prechecks -i multinode [-t <svc>]` | Sets `kolla_action=precheck` (`kolla_ansible/cli/commands.py:99-110`). Read-only ([fact sheet E §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks)), apart from the commands it runs inside existing containers, e.g. `rabbitmqctl list_queues` (`roles/rabbitmq/tasks/precheck.yml:110-116`). `-t <svc>` skips the `prechecks` role (untagged play, `site.yml:77-86`) but runs `<svc>/precheck.yml`. **Changed in 2025.1:** the two RabbitMQ variable checks of the `prechecks` role are gone; the rabbitmq precheck fails when the queues of the running broker are not of the type the configuration expects, under the tag `rabbitmq-ha-precheck` (`roles/rabbitmq/tasks/precheck.yml:109-164`; [F17](../reference/findings.md#f17)); the supported OS and Ansible versions changed ([fact sheet E §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks)) |

## 2. The first 2025.1 run on a cloud deployed by 2024.1

The first `deploy`, `reconfigure`, `upgrade` or `deploy-containers` that the 2025.1 code runs on a host can restart or
recreate containers whose operator config did not change. Two causes come from the code, and each can be seen before
the run [CODE]. A third applies to every service that `kolla-ansible upgrade` has not reached yet, below the table:

| Cause | Containers | How to see it before the run |
|---|---|---|
| **Unit text** ([F16](../reference/findings.md#f16)). The 2025.1 template adds `PartOf=kolla.target` (`module_utils/kolla_systemd_worker.py:20-40`, line `:27`), and the `common` role installs that target (`roles/common/tasks/config.yml:54-58`); `check_unit_change` compares the whole file (`:155-168`). A container that the 2025.1 code has not yet created or restarted still has the unit that 2024.1 wrote | every long-running container not recreated or restarted by 2025.1 code whose role runs the check step, for example one outside the tags of a partial upgrade. A container recreated or restarted by the upgrade got the new unit then | `grep -L PartOf=kolla.target /etc/systemd/system/kolla-*-container.service`: each file listed differs from the 2025.1 template and its container reports drift. `kolla_set_configs --check` does not show it |
| **Default ulimits** (Docker, hosts outside the Red Hat family). `default_container_dimensions` now sets `nofile` 1048576 with Docker on every host (`group_vars/all.yml:201-224`); in 2024.1 it was empty outside the Red Hat family. `compare_dimensions` compares ulimits (`module_utils/kolla_container_worker.py:274-303, :326-336`) | every container created by 2024.1 whose service uses `default_container_dimensions`, most of them (e.g. `roles/glance/defaults/main.yml:168`): it differs and is **recreated**, not only restarted. The Podman worker filters these limits out of the comparison (`module_utils/kolla_podman_worker.py:219-228, :484-500`), so Podman hosts are not affected | `docker inspect -f '{{.HostConfig.Ulimits}}' <container>` prints `[]` for a container created by 2024.1 on such a host. `kolla_set_configs --check` does not show it |

**Image tag.** `openstack_release` defaults to `2025.1` (`group_vars/all.yml:795-797`) and every image tag follows it
(e.g. `roles/keystone/defaults/main.yml:98-100`). The check step compares the image
(`module_utils/kolla_container_worker.py:75`), and the restart handler recreates a container whose image differs,
pulling it first when absent (`module_utils/kolla_docker_worker.py:352-372`). So a `deploy`, `reconfigure` or
`deploy-containers` moves every service that `kolla-ansible upgrade` has not reached (the whole cloud before the
upgrade, the services outside the tags after `upgrade -t <svc>`) to its 2025.1 image through the deploy path, without
the role's upgrade tasks (e.g. `roles/keystone/tasks/upgrade.yml:23-34`). `kolla_set_configs --check` does not show it;
compare the image tag of each running container (`docker ps`) with the 2025.1 tag. Run `kolla-ansible upgrade` for
those services first.

A container recreated or restarted by 2025.1 code gets the new unit (`module_utils/kolla_systemd_worker.py:173-186`,
called on create and restart, `module_utils/kolla_docker_worker.py:350, :395, :462`), so the unit cause appears once.
[NOT AVAILABLE] What these restarts and recreations do to the running VMs: the sources do not establish it. The
checklist for that run is in [Pre-execution checklist
§2](pre-execution-checklist.md#2-first-20251-run-on-a-cloud-deployed-by-20241).

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
- [Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)
  — the unit template and the default ulimits behind §2
- [Technical findings F14, F16, F17](../reference/findings.md#f14) — the blind spots of the check, the unit-text
  drift and the RabbitMQ queue checks
- [Fact sheet E
  §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks) —
  what `prechecks` checks
- [Open questions Q9](../troubleshooting/open-questions.md#q9) — check mode (`--check --diff`) usability:
  [NOT AVAILABLE]
- [2024.1 predict and inspect a run](../../2024.1/operations/predict-a-run/) — the same page for 2024.1
