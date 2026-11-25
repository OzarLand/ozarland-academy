---
title: Conventions and evidence labels
description: The two evidence labels of the 2025.1 study, the impact classes shown on operation pages with the sections that support them, and how the pages are built.
tags: [evidence, risk]
remember:
  - "The 2025.1 study rests only on reading source code; nothing was run against a host, and no run is used as evidence."
  - "<strong>CODE</strong> means shown by the 2025.1 sources, with a <code>path:line</code> citation nearby."
  - "<strong>NOT AVAILABLE</strong> means the sources do not establish it."
  - "An impact class says that at least one command of the page has that impact, not that all do."
  - "<code>genconfig</code> no longer pulls the fluentd image, but it can restart two containers in narrow cases: <code>placement-api</code> with the Apache WSGI provider, and <code>cinder-volume</code> with Huawei XML files. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "What does the evidence label <span class=\"ev ev-code\">CODE</span> mean?"
    options: ["It was observed during a test run on a host", "It is shown by the 2025.1 sources, with a <code>path:line</code> citation nearby"]
    answer: 1
    explain: "<span class=\"ev ev-code\">CODE</span> means shown by the sources, with a <code>path:line</code> citation nearby. The study rests only on reading source code; nothing was run against a host, and no run is used as evidence."
    see: "evidence-labels"
  - q: "What does the evidence label <span class=\"ev ev-na\">NOT AVAILABLE</span> mean?"
    options: ["The feature does not exist in this release", "The command failed when it was tried", "The sources do not establish it"]
    answer: 2
    explain: "<span class=\"ev ev-na\">NOT AVAILABLE</span> means the sources do not establish it."
    see: "evidence-labels"
  - q: "An operation page carries an impact class. What does that class say?"
    options: ["That at least one command of the page has that impact", "That every command of the page has that impact"]
    answer: 0
    explain: "A page can carry several classes: a class says that at least one command of the page has that impact, not that all do."
    see: "operation-impact-classes"
  - q: "In 2025.1, can <code>genconfig</code> (class <code>writes-config</code>) restart a container?"
    options: ["Never: no task of the config step notifies a handler any more", "In two narrow cases: two config tasks still notify a restart handler that has no guard for <code>kolla_action=config</code>"]
    answer: 1
    explain: "Almost every role stopped notifying handlers from its config step, and most handlers dropped their <code>kolla_action != \"config\"</code> guard. Two config tasks still notify: the Placement WSGI file (only with <code>placement_wsgi_provider: apache</code>) and the Cinder Huawei XML files; their handlers have no guard <span class=\"ev ev-code\">CODE</span>."
    see: "operation-impact-classes"
---

# Conventions and evidence labels

This page defines the two evidence labels used on every page of the 2025.1 study and the impact classes shown on
operation pages. It also says how the pages are built.

> [!NOTE]
> **Key answers**
>
> - **Two labels only:** [CODE], shown by the 2025.1 sources with a `path:line` citation nearby, and
>   [NOT AVAILABLE], not established by them ([Evidence labels](#evidence-labels)).
> - **An impact class is a "can":** it says that at least one command of the page has that impact
>   ([Operation impact classes](#operation-impact-classes)).
> - **Changed in 2025.1 for `writes-config`:** `genconfig` no longer pulls the fluentd image, but two config tasks can
>   still restart a container [CODE] ([Operation impact classes](#operation-impact-classes)).
> - **Changed in 2025.1:** the CLI is a Python program, so commands are cited in `kolla_ansible/cli/commands.py`, not
>   in `tools/kolla-ansible`, which no longer exists.

## Evidence labels

The same two labels are used everywhere, and this is their single definition. The study rests only on reading source
code; nothing was run against a host, and no run is used as evidence.

- **[CODE]** shown by the sources, with a `path:line` citation nearby: kolla-ansible `2025.1-eom` (commit `7222f0f`;
  unprefixed paths, relative to `ansible/`, plus `kolla_ansible/...`, `setup.cfg` and `requirements.txt` at the root
  of the repository), the kolla image repository `2025.1-eom` when the path has a `kolla` prefix (e.g. kolla
  `docker/base/set_configs.py:645-666`), ansible-collection-kolla `2025.1-eom` when the path has an
  `ansible-collection-kolla` prefix, the Ansible source when the path has an `ansible-core 2.18.20` prefix or starts
  with `lib/ansible/`, and the `--list-tags` and `--list-tasks` listings in
  [Ansible listings](../reference/listings/index.md) (ansible-core 2.18.20's own parse of the playbooks).
- **[NOT AVAILABLE]** the sources do not establish it.

The fact sheets use the words FACT and NOT AVAILABLE for the same two levels.

Kolla-Ansible 2025.1 requires ansible-core 2.17 to 2.18 (`requirements.txt:14`, `ansible-core>=2.17,<2.19`). Unlike
2024.1, the CLI does not check the version when it runs: there is no version test in `kolla_ansible/`. Only 2.18.20
was read, so a statement about ansible-core holds for 2.18.20, and what 2.17 does is [NOT AVAILABLE].

## Operation impact classes

An operation page lists its impact classes in its front matter, and the site shows them under the page title. A page
can carry several classes: a class says that at least one command of the page has that impact, not that all do. A class
is used only where the corpus supports it:

| Class | Meaning | Support in the corpus |
|---|---|---|
| `read-only` | The corpus says the command changes nothing. | `prechecks` (`kolla_ansible/cli/commands.py:99-110`, `kolla_action=precheck`): the row "Pre-deployment checks" of [Predict and inspect a run](../operations/predict-a-run.md) and [fact sheet E §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks). The task files it reaches (`roles/prechecks/tasks/*.yml`, every `roles/*/tasks/precheck.yml`, `roles/service-precheck/tasks/main.yml`, `roles/neutron/tasks/neutron_plugin_agent_check.yml`) use only `wait_for`, `assert`, `fail`, `stat`, `getent`, `group_by`, `set_fact`, `kolla_container_facts` and `command`/`shell` calls that read state, such as `{{ kolla_container_engine }} --version` with `changed_when: false` (`roles/prechecks/tasks/service_checks.yml:9-14`), the RabbitMQ queue listing (`roles/rabbitmq/tasks/precheck.yml:113`) or the HAProxy `show stat` read (`roles/loadbalancer/tasks/precheck.yml:230-235`) [CODE]. `kolla_container_volume_facts`, used in 2024.1, no longer exists (no such file under `library/`). The new `check` command is read-only too in the same sense: its `service-check` role only reads container facts and fails on a missing, stopped or unhealthy container (`roles/service-check/tasks/main.yml:2-40`) [CODE]. On the same page, `genconfig` writes config (next class), and whether a check-mode run fails or gives partial results is [NOT AVAILABLE]. |
| `writes-config` | The command renders config and restarts no container, except in the cases named here. | `genconfig` (`kolla_action=config`, `kolla_ansible/cli/commands.py:113-125`): row `genconfig` of [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) and step 1 of the [Pre-execution checklist](../operations/pre-execution-checklist.md). **Changed in 2025.1:** the config step of almost every role notifies no handler any more, and most handlers lost their `when: kolla_action != "config"` guard (19 guarded handlers are left, in `roles/etcd`, `roles/loadbalancer` and `roles/nova-cell`). Two config tasks still notify an unguarded handler, so `genconfig` can restart these containers [CODE]: `placement-api`, when `placement_wsgi_provider` is `apache` and its WSGI file changes (`roles/placement/tasks/config.yml:58-74`; handler `roles/placement/handlers/main.yml:2-14`; the default provider is `uwsgi`, `roles/placement/defaults/main.yml:156`), and `cinder-volume`, when `cinder_backend_huawei` is on and a Huawei XML file changes (`roles/cinder/tasks/config.yml:12-15`, `roles/cinder/tasks/external_huawei.yml:2-11`; handler `roles/cinder/handlers/main.yml:30-45`). The config tasks of the fake drivers (`roles/neutron/tasks/config-neutron-fake.yml`, `roles/nova-cell/tasks/config-nova-fake.yml`) also notify; they are test drivers and were not traced. **Also changed:** the common role's config step no longer pulls the fluentd image: 2025.1 `roles/common/tasks/config.yml` has no `ensure_image` task [CODE]. |
| `pulls-images` | The command downloads images; running containers do not change. | `pull` never changes running containers [CODE]: every role's `pull.yml` except ceph-rgw's imports `service-images-pull`, whose only task runs `kolla_container` `pull_image` for each enabled container mapped to the host and notifies no handler (`roles/service-images-pull/tasks/main.yml:2-17`); ceph-rgw's is empty. Swift, which pulled its images in its own `pull.yml` in 2024.1, has no role in 2025.1. See [Update container images §1.1](../operations/update-container-images.md#11-images), row `pull` of [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) and [R11](../risk/risk-register.md#r11). |
| `restarts-on-drift` | The command can restart containers, only if drift is detected. | The "Restarts" convention of the [command sections](../operations/index.md#conventions-used-by-the-command-sections) and the definition of [drift](../operations/index.md#drift); the "Containers that can restart" column of [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table). The drift test is `compare_container`, the same for the Docker and the Podman worker (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_podman_worker.py:301-308`), run for every role by the shared `service-check-containers` role (`roles/service-check-containers/tasks/main.yml:4-29`) [CODE]. |
| `recreates-containers` | The command recreates containers (stop, rm, create, start) when their image or parameters differ. | The entry "restart vs recreate" of the [Glossary](../reference/glossary.md); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [R12](../risk/risk-register.md#r12). The recreate branch is `module_utils/kolla_docker_worker.py:364-372` (Docker) and `module_utils/kolla_podman_worker.py:618-623` (Podman) [CODE]. |
| `critical` | The page covers an operation rated Critical in the risk register. | The Severity column of the [Risk register](../risk/risk-register.md#matrix). |
| `maintenance-window` | The corpus asks to plan the operation as a maintenance. | The Precautions of the risks that say "Plan as a maintenance" or "Maintenance window" in the [Risk register](../risk/risk-register.md#matrix). |
| `recovery` | The page is a backup or recovery procedure. | `mariadb-backup` and `mariadb-recovery`, two commands of the CLI that run their own playbooks (`kolla_ansible/cli/commands.py:437-481`; `setup.cfg:72-73`; `ansible/mariadb_backup.yml`, `ansible/mariadb_recovery.yml`) [CODE]. **Changed in 2025.1:** the commands are spelled with a hyphen; `mariadb_backup` and `mariadb_recovery` are not commands of the CLI any more. See [Database operations](../operations/database-operations.md), [fact sheet E §9](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only) and the rows "backup" and "recovery" of [fact sheet B §1.3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#13-task-flow-per-kolla_action). |

## How pages are built

- **Every page:** a title, an introduction of one to three sentences, a "Key answers" note when the study has one for
  the page, the body, and a closing "Related" list.
- **Callouts** are the five GitHub alerts: note, tip, important, warning and caution.
- **Commands** are written in the 2025.1 syntax, the action first: `kolla-ansible <action> <arguments>`
  (`kolla_ansible/cli/commands.py`; release note `python-cli-3e568065b8706e73.yaml`). Where a page needs the 2024.1
  form, it says so.
- **Operation pages:** the commands come first, in section 1 or directly under the introduction, and follow the
  [conventions of the command sections](../operations/index.md#conventions-used-by-the-command-sections). The impact
  classes are shown under the title. Risks are cited by number and link to the [Risk
  register](../risk/risk-register.md). R25 ("`-t common` believed to reconfigure fluentd/cron") does not apply to
  2025.1: `common` is a play of its own, tagged `common` (`site.yml:88-103`), so `-t common` runs it [CODE]. Risks and
  verification steps, when a page has them, are in its last numbered sections.

## Related

- [Method and limits of the study](../reference/method-and-limits.md) — how the sources were read, and the limits of
  a source-only study
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Glossary](../reference/glossary.md) — the terms the study uses, with the place where each is defined
- [Operations](../operations/index.md) — the operation pages, each with its impact classes and risks
- [Risk register](../risk/risk-register.md) — the risks, with their likelihood and severity
