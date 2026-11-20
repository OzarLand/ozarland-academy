---
title: Conventions and evidence labels
description: The two evidence labels of the 2024.1 study, the impact classes shown on operation pages with the sections that support them, and how the pages are built.
tags: [evidence, risk]
remember:
  - "The 2024.1 study rests only on reading source code; nothing was run against a host, and no run is used as evidence."
  - "<strong>CODE</strong> means shown by the 2024.1 sources, with a <code>path:line</code> citation nearby."
  - "<strong>NOT AVAILABLE</strong> means the sources do not establish it."
  - "An impact class says that at least one command of the page has that impact, not that all do."
  - "<code>pull</code> downloads images and never changes running containers; <code>genconfig</code> restarts no container but can pull the fluentd image when it is absent. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "What does the evidence label <span class=\"ev ev-code\">CODE</span> mean?"
    options: ["It was observed during a test run on a host", "It is shown by the 2024.1 sources, with a <code>path:line</code> citation nearby"]
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
  - q: "In 2024.1, can <code>genconfig</code> (class <code>writes-config</code>) download an image?"
    options: ["No: it only writes files", "Yes: the common role's config step pulls the fluentd image when it is not on the host, but no container is restarted"]
    answer: 1
    explain: "The common config step runs <code>kolla_container</code> <code>ensure_image</code> on the fluentd image whenever fluentd is enabled, and that pulls it when it is absent. Every handler that restarts a container is skipped under <code>kolla_action=config</code> <span class=\"ev ev-code\">CODE</span>."
    see: "operation-impact-classes"
---

# Conventions and evidence labels

This page defines the two evidence labels used on every page of the 2024.1 study and the impact classes shown on
operation pages. It also says how the pages are built.

> [!NOTE]
> **Key answers**
>
> - **Two labels only:** [CODE], shown by the 2024.1 sources with a `path:line` citation nearby, and
>   [NOT AVAILABLE], not established by them ([Evidence labels](#evidence-labels)).
> - **An impact class is a "can":** it says that at least one command of the page has that impact
>   ([Operation impact classes](#operation-impact-classes)).
> - **Changed in 2024.1 for `writes-config`:** `genconfig` still restarts no container, but it can pull the fluentd
>   image when the image is absent [CODE] ([Operation impact classes](#operation-impact-classes)).

## Evidence labels

The same two labels are used everywhere, and this is their single definition. The study rests only on reading source
code; nothing was run against a host, and no run is used as evidence.

- **[CODE]** shown by the sources, with a `path:line` citation nearby: kolla-ansible `2024.1-eom` (commit `890396f`;
  unprefixed paths, relative to `ansible/`, plus `tools/...`), the kolla image repository `2024.1-eom` when the path
  has a `kolla` prefix (e.g. kolla `docker/base/set_configs.py:556-559`), ansible-collection-kolla `2024.1-eom` when
  the path has an `ansible-collection-kolla` prefix (e.g. ansible-collection-kolla
  `roles/baremetal/tasks/main.yml:2-3`),
  the Ansible source when the path has an `ansible-core 2.16.20` prefix or starts with `lib/ansible/`, and the
  `--list-tags` and `--list-tasks` listings in [Ansible listings](../reference/listings/index.md) (ansible-core
  2.16.20's own parse of the playbooks).
- **[NOT AVAILABLE]** the sources do not establish it.

The fact sheets use the words FACT and NOT AVAILABLE for the same two levels.

Kolla-Ansible 2024.1 accepts ansible-core 2.15 to 2.16 (`tools/kolla-ansible:10-11`); only 2.16.20 was read, so a
statement about ansible-core holds for 2.16.20, and what 2.15 does is [NOT AVAILABLE].

## Operation impact classes

An operation page lists its impact classes in its front matter, and the site shows them under the page title. A page
can carry several classes: a class says that at least one command of the page has that impact, not that all do. A class
is used only where the corpus supports it:

| Class | Meaning | Support in the corpus |
|---|---|---|
| `read-only` | The corpus says the command changes nothing. | `prechecks` (`tools/kolla-ansible:444-446`, `kolla_action=precheck`): the row "Pre-deployment checks" of [Predict and inspect a run](../operations/predict-a-run.md) and [fact sheet E §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks). The task files it reaches (`roles/prechecks/tasks/*.yml`, every `roles/*/tasks/precheck.yml`, `roles/service-precheck/tasks/main.yml`, `roles/neutron/tasks/neutron_plugin_agent_check.yml`) use only `wait_for`, `assert`, `fail`, `stat`, `getent`, `group_by`, `set_fact`, `kolla_container_facts`, `kolla_container_volume_facts` and `command`/`shell` calls that read state, such as `{{ kolla_container_engine }} --version` with `changed_when: false` (`roles/prechecks/tasks/service_checks.yml:11-13`) or the new RabbitMQ queue listing (`roles/rabbitmq/tasks/precheck.yml:134-136`) [CODE]. On the same page, `genconfig` writes config (next class), and whether a check-mode run fails or gives partial results is [NOT AVAILABLE]. |
| `writes-config` | The command renders config and restarts no container. | `genconfig` (`kolla_action=config`, `tools/kolla-ansible:557-560`): row `genconfig` of [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) (config written, all container restarts skipped) and step 1 of the [Pre-execution checklist](../operations/pre-execution-checklist.md). Every handler that starts, restarts or recreates a container with `kolla_container` carries `when: kolla_action != "config"`, except keystone's two database-upgrade handlers, guarded by `kolla_action == "upgrade"` (`roles/keystone/handlers/main.yml:5-27,77-98`), MariaDB's first-node start, notified only from `roles/mariadb/tasks/bootstrap_cluster.yml:2-23`, and etcd's upgrade restart, an `include_tasks` handler guarded by `kolla_action == "upgrade"` (`roles/etcd/handlers/main.yml:29-36`) [CODE]. The Ussuri exception, the nova-hyperv role, does not exist in 2024.1 (no such directory under `ansible/roles/`). **Changed in 2024.1:** the command is not limited to files any more. The common role's config step runs `kolla_container` `ensure_image` on the fluentd image whenever `enable_fluentd` is on (`roles/common/tasks/config.yml:42-51`), and that pulls the image when it is not on the host (`module_utils/kolla_docker_worker.py:501-503`) [CODE]. No running container changes. |
| `pulls-images` | The command downloads images; running containers do not change. | `pull` never changes running containers [CODE]: every role's `pull.yml` except swift's and ceph-rgw's imports `service-images-pull`, whose only task runs `kolla_container` `pull_image` for each enabled container mapped to the host and notifies no handler (`roles/service-images-pull/tasks/main.yml:2-18`); swift's `pull.yml` runs `pull_image` directly, one task per image (`roles/swift/tasks/pull.yml:2-74`), and ceph-rgw's is empty. See [Update container images §1.1](../operations/update-container-images.md#11-images), row `pull` of [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) and [R11](../risk/risk-register.md#r11). |
| `restarts-on-drift` | The command can restart containers, only if drift is detected. | The "Restarts" convention of the [command sections](../operations/index.md#conventions-used-by-the-command-sections) and the definition of [drift](../operations/index.md#drift); the "Containers that can restart" column of [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table). The drift test is `compare_container`, the same for the Docker and the Podman worker (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_podman_worker.py:294-301`) [CODE]. |
| `recreates-containers` | The command recreates containers (stop, rm, create, start) when their image or parameters differ. | The entry "restart vs recreate" of the [Glossary](../reference/glossary.md); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [R12](../risk/risk-register.md#r12). The recreate branch is `module_utils/kolla_docker_worker.py:353-362` (Docker) and `module_utils/kolla_podman_worker.py:516-521` (Podman) [CODE]. |
| `critical` | The page covers an operation rated Critical in the risk register. | The Severity column of the [Risk register](../risk/risk-register.md#matrix): R7, R12, R14, R15 and R16. |
| `maintenance-window` | The corpus asks to plan the operation as a maintenance. | The Precautions of [R3](../risk/risk-register.md#r3) ("Plan as a maintenance") and of [R10](../risk/risk-register.md#r10) ("Maintenance window"). |
| `recovery` | The page is a backup or recovery procedure. | `mariadb_backup` and `mariadb_recovery`, two commands of the wrapper that run their own playbooks (`tools/kolla-ansible:448-456`; `ansible/mariadb_backup.yml`, `ansible/mariadb_recovery.yml`) [CODE]: [Database operations](../operations/database-operations.md), [fact sheet E §9](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only) and the rows "backup" and "recovery" of [fact sheet B §1.3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#13-task-flow-per-kolla_action). |

## How pages are built

- **Every page:** a title, an introduction of one to three sentences, a "Key answers" note when the study has one for
  the page, the body, and a closing "Related" list.
- **Callouts** are the five GitHub alerts: note, tip, important, warning and caution.
- **Operation pages:** the commands come first, in section 1 or directly under the introduction, and follow the
  [conventions of the command sections](../operations/index.md#conventions-used-by-the-command-sections). The impact
  classes are shown under the title. Risks are cited by number (R1 to R30) and link to the [Risk
  register](../risk/risk-register.md). R25 ("`-t common` believed to reconfigure fluentd/cron") does not apply to
  2024.1: `common` is a play of its own, tagged `common` (`site.yml:88-103`), so `-t common` runs it [CODE]. Risks and
  verification steps, when a page has them, are in its last numbered sections.

## Related

- [Method and limits of the study](../reference/method-and-limits.md) — how the sources were read, and the limits of
  a source-only study
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Glossary](../reference/glossary.md) — the terms the study uses, with the place where each is defined
- [Operations](../operations/index.md) — the operation pages, each with its impact classes and risks
- [Risk register](../risk/risk-register.md) — the 30 risks, with their likelihood and severity (R25 does not apply to
  2024.1)
