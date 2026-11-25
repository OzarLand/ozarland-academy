---
title: Operations
description: Catalogue of the 2025.1 Day-2 operation pages with their commands, impact classes and risks, and the assumptions and conventions they share.
tags: [reconfigure, deploy, upgrade, genconfig, deploy-containers, pull, serial, limit, max-fail-percentage, risk]
---

# Operations

What Kolla-Ansible 2025.1 commands do when they run against a live platform, read from the source of the **unmodified
`site.yml`**, its roles and ansible-core 2.18.20. Nothing was run against a host.

<img src="../assets/images/S3-predict-a-run.webp" width="1536" height="1024" loading="lazy" alt="LUMO holds a parchment beside a small brass server model on a workbench while Jo, carrying a crate, waits before touching anything.">

Real `kolla-ansible` (2025.1) invocations with what they select, their scope and their impact. Changed in 2025.1: the
CLI is a Python program, and its options follow the sub-command (`kolla-ansible reconfigure -i multinode -t keystone`).

> [!NOTE]
> **Key answers**
>
> - **What restarts, changed in 2025.1:** only the containers that drifted. The restart decision is the shared
>   `service-check-containers` step, which notifies only the containers it found changed; loop-notify is gone
>   ([F1](../reference/findings.md#f1), [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)).
> - **A service tag also touches** Keystone registration, for most services DB creation and schema sync, and hosts
>   outside `--limit`; it still does not touch `common` ([Reconfigure a single service
>   §2](reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)). Changed in 2025.1: it rewrites the
>   service's HAProxy frontend file but no longer restarts HAProxy; the change waits for `-t haproxy` or an untagged
>   run ([F18](../reference/findings.md#f18)).
> - **Batching, changed in 2025.1:** `reconfigure` and `upgrade` always run with `kolla_serial=0`, whatever `-e` says;
>   use `deploy -e kolla_serial=N`, which runs the same tasks ([F19](../reference/findings.md#f19), [Write config first,
>   apply in controlled batches §1.2](controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure)).
>   Every play sets `max_fail_percentage`, default 100, which never stops a play early; lower it to stop a rolling run
>   on failures ([§1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
> - **First 2025.1 run on a cloud deployed by 2024.1:** expect restarts whose operator config did not change: the
>   systemd unit text changed and, with Docker outside the Red Hat family, the default ulimits
>   ([F16](../reference/findings.md#f16)); classic RabbitMQ queues must be migrated first
>   ([R27](../risk/risk-register.md#r27)); with OVN, the chassis move to the Southbound relays
>   ([R33](../risk/risk-register.md#r33)). How to see them before the run: [Predict and inspect a run
>   §2](predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241); what to settle first: [Pre-execution
>   checklist §2](pre-execution-checklist.md#2-first-20251-run-on-a-cloud-deployed-by-20241).
> - **Recommended pattern:** `genconfig`, then `deploy-containers --limit` batch by batch, with its caveats [CODE]
>   ([Write config first, apply in controlled batches
>   §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). Why a small change can create a
>   large workload: [Why a small change creates a large workload](../risk/small-change-large-workload.md).
> - **Keep the frontend file untouched:** `--skip-tags haproxy` ([Reconfigure a single service
>   §1.2](reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)). **Push `common` changes:**
>   `-t common`, which runs the common play ([Apply `common` changes (fluentd, cron, kolla_toolbox)
>   §1.1](apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)); changed in 2025.1, its config
>   step no longer pulls the fluentd image.
> - **Add a compute:** `bootstrap-servers`, `pull` and `deploy`, each with `--limit` ([Add a compute node
>   §1.1](add-a-compute-node.md#11-add-a-compute-node)). **Per-tag quick lookup** of hosts touched, possible restarts
>   and one-shot containers: [Command quick lookup by tag](command-quick-lookup.md).

## Operations catalogue

One row per operation page, in the order of the navigation. The commands are copied from each page. The impact classes
are defined in [Operation impact classes](../start/conventions.md#operation-impact-classes). The risk numbers are those
the page cites, in its text or in its "Related" list.

| Operation | Commands covered | Impact | Risks |
|---|---|---|---|
| [Pre-execution checklist](pre-execution-checklist.md) | `kolla-ansible genconfig`<br>`docker exec -u root <c> /usr/local/bin/kolla_set_configs --check`<br>`kolla-ansible pull`<br>`kolla-ansible mariadb-backup`<br>`kolla-ansible prechecks` (first 2025.1 run)<br>and the `openstack` checks of its steps 5 and 6 | `writes-config` | – |
| [Predict and inspect a run](predict-a-run.md) | `ansible-playbook -i multinode --list-tags …/site.yml`<br>`ansible-playbook -i multinode -t nova --list-hosts …/site.yml`<br>`kolla-ansible deploy -i multinode --list-tasks`<br>`kolla-ansible genconfig -i multinode [-t <svc>] [--limit <hosts>]`<br>`docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` (Podman: `podman exec -u root …`)<br>`kolla-ansible reconfigure -i multinode --check --diff`<br>`kolla-ansible prechecks -i multinode [-t <svc>]` | `read-only`, `writes-config` | – |
| [Reconfigure a single service](reconfigure-a-service.md) | `kolla-ansible reconfigure -i multinode -t keystone`<br>`kolla-ansible reconfigure -i multinode -t nova --skip-tags haproxy` | `restarts-on-drift` | [R8](../risk/risk-register.md#r8), [R14](../risk/risk-register.md#r14), [R19](../risk/risk-register.md#r19), [R20](../risk/risk-register.md#r20), [R23](../risk/risk-register.md#r23), [R24](../risk/risk-register.md#r24) |
| [Reconfigure Nova](reconfigure-nova.md) | `kolla-ansible reconfigure -i multinode -t nova`<br>`kolla-ansible reconfigure -i multinode -t nova-api`<br>`kolla-ansible reconfigure -i multinode -t nova-cell`<br>`kolla-ansible deploy -i multinode -t nova -e kolla_serial=10` | `restarts-on-drift` | [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2), [R3](../risk/risk-register.md#r3), [R24](../risk/risk-register.md#r24) |
| [Reconfigure Neutron](reconfigure-neutron.md) | `kolla-ansible reconfigure -i multinode -t neutron`<br>`kolla-ansible deploy -i multinode -t neutron --limit network01`<br>`kolla-ansible deploy -i multinode -t openvswitch --limit compute042`<br>`kolla-ansible deploy -i multinode -t neutron -e kolla_serial=10` | `restarts-on-drift`, `critical` | [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7) |
| [Apply `common` changes (fluentd, cron, kolla_toolbox)](apply-common-changes.md) | `kolla-ansible reconfigure -i multinode -t common`<br>`kolla-ansible reconfigure -i multinode -t common --limit 'compute[0:49]'` | `restarts-on-drift` | [R2](../risk/risk-register.md#r2), [R25](../risk/risk-register.md#r25) |
| [Write config first, apply in controlled batches](controlled-batches.md) | `kolla-ansible genconfig -i multinode -t nova-cell`<br>`kolla-ansible deploy-containers -i multinode -t nova-cell --limit 'compute[0:9]'`<br>`kolla-ansible deploy-containers -i multinode -t nova-cell --limit 'compute[10:19]'`<br>`kolla-ansible deploy -i multinode -t nova -e kolla_serial=10`<br>`kolla-ansible deploy -i multinode -t nova -e kolla_serial=10 -e kolla_max_fail_percentage=0` | `writes-config`, `restarts-on-drift` | [R1](../risk/risk-register.md#r1), [R32](../risk/risk-register.md#r32) |
| [Update container images](update-container-images.md) | `kolla-ansible pull -i multinode`<br>`kolla-ansible pull -i multinode -t nova --limit compute`<br>`kolla-ansible upgrade -i multinode`<br>`kolla-ansible upgrade -i multinode -t nova --limit 'compute[0:19]'`<br>`kolla-ansible prune-images -i multinode --yes-i-really-really-mean-it` | `pulls-images`, `recreates-containers`, `critical` | [R7](../risk/risk-register.md#r7), [R11](../risk/risk-register.md#r11), [R12](../risk/risk-register.md#r12), [R13](../risk/risk-register.md#r13), [R17](../risk/risk-register.md#r17) |
| [Add a compute node](add-a-compute-node.md) | `kolla-ansible bootstrap-servers -i multinode --limit compute004`<br>`kolla-ansible pull -i multinode --limit compute004`<br>`kolla-ansible deploy -i multinode --limit compute004` | – | [R14](../risk/risk-register.md#r14), [R23](../risk/risk-register.md#r23) |
| [Change control-plane membership](change-control-plane-membership.md) | no command line in its command section; its scenario reads `-t nova,neutron reconfigure` | `restarts-on-drift`, `maintenance-window` | [R3](../risk/risk-register.md#r3), [R4](../risk/risk-register.md#r4) |
| [Database operations](database-operations.md) | `kolla-ansible mariadb-backup -i multinode`<br>`kolla-ansible mariadb-recovery -i multinode` | `recovery` | [R15](../risk/risk-register.md#r15), [R18](../risk/risk-register.md#r18) |
| [Stop and destroy](stop-and-destroy.md) | `kolla-ansible stop -i multinode --yes-i-really-really-mean-it -t heat --limit control03`<br>`kolla-ansible destroy -i multinode --yes-i-really-really-mean-it` | `critical` | [R15](../risk/risk-register.md#r15), [R16](../risk/risk-register.md#r16) |
| [Command quick lookup by tag](command-quick-lookup.md) | `-t <tag> reconfigure` for 15 tags<br>`reconfigure` (no tag)<br>`deploy-containers -t X`<br>`genconfig -t X`<br>`pull -t X` | `restarts-on-drift`, `writes-config`, `pulls-images` | by tag, in the "Risks" bullet of the [component pages](../components/index.md) |

Two changes of the 2025.1 CLI have no operation page: the new `migrate-container-engine`, which moves every container from one
engine to the other without asking for confirmation ([R31](../risk/risk-register.md#r31)), and the removal of
`rabbitmq-upgrade`, which the RabbitMQ version check still names ([R28](../risk/risk-register.md#r28)).

## Assumed deployment

Every scenario assumes the same deployed state: 3 controllers, 2 network nodes, 3 computes, 1 storage node and 1
monitoring node, with Keystone, Glance, Placement, Nova, Neutron/OVS, Cinder/LVM, Heat and Horizon. The container engine
is Docker, the 2025.1 default (`kolla_container_engine: "docker"`, `group_vars/all.yml:100`) [CODE]; where a page
describes the Podman path, it says so. Changed in 2025.1: ProxySQL is on by default in front of MariaDB, and RabbitMQ
4.0 is the default image; Swift is no longer deployed ([Swift](../components/swift.md)).

## Conventions used by the command sections

These two lists apply to the command sections of every operation page and to the [Command quick lookup by
tag](command-quick-lookup.md).

The examples assume:

- the inventory is `/etc/kolla/multinode` (adapt `-i`);
- `globals.yml` and `passwords.yml` are in `/etc/kolla`;
- Ansible is ansible-core 2.18 (`requirements.txt:14` accepts 2.17 to 2.18; only 2.18.20 was read).

Conventions:

- **Scope** = plays and hosts touched.
- **Restarts** = containers that *can* restart (only if drift is detected).
- **One-shot** = bootstrap containers that run regardless of drift.

## Drift

Drift means what `compare_container` detects: a missing container, a changed image or container parameter (16
comparisons), `kolla_set_configs --check` reporting a change, or a systemd unit file whose text differs from the
rendered template (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_container_worker.py:67-89`)
[CODE]. The check reads `kolla_set_configs --check` per engine. With Docker, exit code 1 or 137, or a client error from
the exec, is drift (`module_utils/kolla_docker_worker.py:146-181`). With Podman, a container that is not running is
drift, 1 is drift, and any other non-zero code fails the task (`module_utils/kolla_podman_worker.py:524-555`)
([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).
Changed in 2025.1, the check also reports a command that differs from `/run_command` and a dropped `config.json` entry
([F14](../reference/findings.md#f14), [F21](../reference/findings.md#f21)). The unit-file comparison is what makes the
first 2025.1 check report drift for a container whose unit 2024.1 wrote ([F16](../reference/findings.md#f16)).

## Code guarantees and environment dependence

On the operation pages:

- **The code guarantees** = what Kolla will do (tasks, restarts) given the inputs.
- **Depends on the environment** = what that does to VMs and APIs; mostly [NOT AVAILABLE] in these sources.

These two notions head the columns of the tables in [Reconfigure Nova
§5](reconfigure-nova.md#5-running-vms-live-migration-scheduling) ("Guaranteed by code", "Depends on environment") and
[Reconfigure Neutron §4](reconfigure-neutron.md#4-impact-on-networking) ("code-guaranteed", "environment-dependent").

The evidence labels **[CODE]** and **[NOT AVAILABLE]** are defined once, in the [Conventions and evidence
labels](../start/conventions.md#evidence-labels).

## Three mechanisms that explain almost every surprise

Three mechanisms explain almost every surprise on the operation pages, so they are restated here, each with the section
that establishes it. The 2024.1 list had loop-notify as its second item; it is gone in 2025.1.

1. **Config drift ⇒ full container stop/start.** It is never a reload. Still holds in 2025.1: the stop timeout is
   `docker_graceful_timeout`, **60 s** by default (`group_vars/all.yml:148`), passed to the module as
   `graceful_timeout` in `docker_common_options` (`group_vars/all.yml:160`). Each container runs under a
   `kolla-<name>-container.service` systemd unit, and a restart goes through that unit
   (`module_utils/kolla_docker_worker.py:450-470`, `module_utils/kolla_podman_worker.py:704-719`,
   `module_utils/kolla_systemd_worker.py:107-114`), whose stop is `/usr/bin/${engine} stop ${name} -t
   ${graceful_timeout}` (`module_utils/kolla_systemd_worker.py:33`) ([Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)).
2. **One shared restart decision.** Changed in 2025.1: the config tasks no longer notify handlers; the
   `service-check-containers` step compares each container and notifies only those that changed, so one changed
   container no longer restarts its siblings ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)). A
   service tag no longer restarts HAProxy ([F18](../reference/findings.md#f18)).
3. **Global inputs.** `enable_*` flags, group membership and passwords are rendered into per-host files on every host
   ([Component dependencies §5](../components/dependencies.md#5-compute-node-dependency-summary)).

## Related

- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) (what each tag executes)
- [Risk register](../risk/risk-register.md) (risks [R1–R33](../risk/risk-register.md#r1))
- [Technical findings](../reference/findings.md) (the 2025.1 findings [F18](../reference/findings.md#f18) to
  [F22](../reference/findings.md#f22), and [F16](../reference/findings.md#f16) and [F17](../reference/findings.md#f17)
  behind the first 2025.1 run)
- [Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special) (nova-libvirt restarts)
- [Tag index](../risk/tag-index.md) and [What is not known](../troubleshooting/what-is-not-known.md) (tag index,
  everything marked [NOT AVAILABLE])
- [Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook) (the CLI →
  playbook mapping and the `kolla_serial` rules)
- [Tags](../risk/tags.md) (tag semantics)
- [Conventions and evidence labels](../start/conventions.md#evidence-labels) (evidence labels)
- [Operations (2024.1)](../../2024.1/operations/) (the same catalogue for the previous release)
