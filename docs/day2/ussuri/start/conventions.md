---
title: Conventions and evidence labels
description: The two evidence labels, the impact classes shown on operation pages with the sections that support them, and how the pages are built.
tags: [evidence, risk]
remember:
  - "The study rests only on reading source code; nothing was run against a host, and no run is used as evidence."
  - "<strong>CODE</strong> means shown by the sources, with a <code>path:line</code> citation nearby."
  - "<strong>NOT AVAILABLE</strong> means the sources do not establish it."
  - "An impact class says that at least one command of the page has that impact, not that all do."
  - "<code>pull</code> downloads images and never changes running containers. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "What does the evidence label <span class=\"ev ev-code\">CODE</span> mean?"
    options: ["It was observed during a test run on a host", "It is shown by the sources, with a <code>path:line</code> citation nearby"]
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
---

# Conventions and evidence labels

This page defines the two evidence labels used on every page and the impact classes shown on operation pages. It also
says how the pages are built.

## Evidence labels

The same two labels are used everywhere, and this is their single definition. The study rests only on reading source
code; nothing was run against a host, and no run is used as evidence.

- **[CODE]** shown by the sources, with a `path:line` citation nearby: kolla-ansible `ussuri-eol` (unprefixed paths),
  the kolla image repository `ussuri-eol` when the path has a `kolla` prefix (e.g. kolla
  `docker/base/set_configs.py:407-410`), the Ansible source when the path has an `ansible 2.9.27` prefix (or
  `ansible 2.8.20`, read for comparison), and the `--list-tags` and `--list-tasks` listings in [Ansible
  listings](../reference/listings/index.md) (Ansible's own parse of the playbooks).
- **[NOT AVAILABLE]** the sources do not establish it.

The fact sheets use the words FACT and NOT AVAILABLE for the same two levels.

## Operation impact classes

An operation page lists its impact classes in its front matter, and the site shows them under the page title. A page
can carry several classes: a class says that at least one command of the page has that impact, not that all do. A class
is used only where the corpus supports it:

| Class | Meaning | Support in the corpus |
|---|---|---|
| `read-only` | The corpus says the command changes nothing. | `prechecks`: the row "Pre-deployment checks" of [Predict and inspect a run](../operations/predict-a-run.md) says "Read-only", and [fact sheet E §5](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#5-ansiblerolesprechecks-kolla-ansible-prechecks) found no module that modifies state in the precheck files. The study titled the section that became that page "Inspection (no changes)". On the same page, `genconfig` writes config (next class) and whether a check-mode run fails or gives partial results is [NOT AVAILABLE]. |
| `writes-config` | The command renders config and restarts no Docker container. | `genconfig`: row `genconfig` of [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) (config written, all container restarts skipped) and step 1 of the [Pre-execution checklist](../operations/pre-execution-checklist.md), which also describes the one exception, the handlers of the deprecated nova-hyperv role. |
| `pulls-images` | The command downloads images; running containers do not change. | `pull` never changes running containers [CODE] ([Update container images §1.1](../operations/update-container-images.md#11-images)); row `pull` of [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does); [R11](../risk/risk-register.md#r11). |
| `restarts-on-drift` | The command can restart containers, only if drift is detected. | The "Restarts" convention of the [command sections](../operations/index.md#conventions-used-by-the-command-sections) and the definition of [drift](../operations/index.md#drift); the "Containers that can restart" column of [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table). |
| `recreates-containers` | The command recreates containers (stop, rm, create, start) when their image or parameters differ. | The entry "restart vs recreate" of the [Glossary](../reference/glossary.md); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [R12](../risk/risk-register.md#r12). |
| `critical` | The page covers an operation rated Critical in the risk register. | The Severity column of the [Risk register](../risk/risk-register.md#matrix): R7, R12, R14, R15 and R16. |
| `maintenance-window` | The corpus asks to plan the operation as a maintenance. | The Precautions of [R3](../risk/risk-register.md#r3) ("Plan as a maintenance") and of [R10](../risk/risk-register.md#r10) ("Maintenance window"). |
| `recovery` | The page is a backup or recovery procedure. | `mariadb_backup` and `mariadb_recovery`: [Database operations](../operations/database-operations.md), [fact sheet E §9](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#9-mariadb_backupyml-and-mariadb_recoveryyml-playbook-level-only) and the rows "backup" and "recovery" of [fact sheet B §1.3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#13-task-flow-per-kolla_action). |

## How pages are built

- **Every page:** a title, an introduction of one to three sentences, a "Key answers" note when the study has one for
  the page, the body, and a closing "Related" list.
- **Callouts** are the five GitHub alerts: note, tip, important, warning and caution.
- **Operation pages:** the commands come first, in section 1 or directly under the introduction, and follow the
  [conventions of the command sections](../operations/index.md#conventions-used-by-the-command-sections). The impact
  classes are shown under the title. Risks are cited by number (R1 to R25) and link to the [Risk
  register](../risk/risk-register.md). Risks and verification steps, when a page has them, are in its last numbered
  sections.

## Related

- [Method and limits of the study](../reference/method-and-limits.md) — how the sources were read, and the limits of
  a source-only study
- [What is not known](../troubleshooting/what-is-not-known.md) — everything marked [NOT AVAILABLE], by topic
- [Glossary](../reference/glossary.md) — the terms the study uses, with the place where each is defined
- [Operations](../operations/index.md) — the operation pages, each with its impact classes and risks
- [Risk register](../risk/risk-register.md) — the 25 risks, with their likelihood and severity
