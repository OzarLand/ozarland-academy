---
title: Operations
description: Catalogue of the 2024.1 Day-2 operation pages with their commands, impact classes and risks, and the assumptions and conventions they share.
tags: [reconfigure, deploy, upgrade, genconfig, deploy-containers, pull, loop-notify, limit, max-fail-percentage, risk]
---

# Operations

What Kolla-Ansible 2024.1 commands do when they run against a live platform, read from the source of the **unmodified
`site.yml`**, its roles and ansible-core 2.16.20. Nothing was run against a host.

Real `kolla-ansible` (2024.1) invocations with what they select, their scope and their impact.

> [!NOTE]
> **Key answers**
>
> - **A service tag also touches** the HAProxy frontends of the service, Keystone registration, for most services DB
>   creation and schema sync (Neutron's DB sync on every `deploy` and `reconfigure`), and hosts outside `--limit`.
>   Still holds in 2024.1: it does not touch `common`, because no role has a `meta` dependency on it ([Reconfigure a
>   single service §2](reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)). A controller
>   membership change is a fleet-wide restart event for every messaging consumer; new in 2024.1, the etcd role adds a
>   new member itself ([Change control-plane membership
>   §2](change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)). What adding a
>   compute with `deploy --limit` touches: [Add a compute node §2](add-a-compute-node.md#2-add-a-compute-node).
> - **First 2024.1 run on a cloud deployed by 2023.1:** expect restarts whose operator config did not change: the
>   systemd unit text changed ([F16](../reference/findings.md#f16)), RabbitMQ quorum queues are on by default
>   ([F17](../reference/findings.md#f17)), and `nova_compute` and `cinder_volume` get a new `hostnqn` file. How to see
>   them before the run:
> [Predict and inspect a run §2](predict-a-run.md#2-the-first-20241-run-on-a-cloud-deployed-by-20231);
>   what to settle first:
> [Pre-execution checklist §2](pre-execution-checklist.md#2-first-20241-run-on-a-cloud-deployed-by-20231).
> - **Recommended pattern:** `genconfig`, then `deploy-containers --limit` batch by batch, with its caveats [CODE]
>   ([Write config first, apply in controlled batches
>   §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). New in 2024.1: every play sets
>   `max_fail_percentage`, default 100, which never stops a play early; lower it to stop a rolling run on failures
>   ([§1.3](controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)). Why a small change can create
>   a large workload: [Why a small change creates a large workload](../risk/small-change-large-workload.md).
> - **Leave HAProxy alone:** `--skip-tags haproxy` ([Reconfigure a single service
>   §1.2](reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)). **Push `common` changes:**
>   `-t common`, which runs the common play (`site.yml:88-103`); still in 2024.1, `-t chrony` selects nothing, as there
> is
>   no chrony role ([Apply `common` changes (fluentd, cron, kolla_toolbox)
>   §1.1](apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)). New in 2024.1: the common
>   play's config step can pull the fluentd image, `genconfig` included.
> - **Add a compute:** `bootstrap-servers`, `pull` and `deploy`, each with `--limit` ([Add a compute node
>   §1.1](add-a-compute-node.md#11-add-a-compute-node)). **Per-tag quick lookup** of hosts touched, possible restarts
>   and one-shot containers: [Command quick lookup by tag](command-quick-lookup.md).

## Operations catalogue

One row per operation page, in the order of the navigation. The commands are copied from each page. The impact classes
are defined in [Operation impact classes](../start/conventions.md#operation-impact-classes). The risk numbers are those
the page cites, in its text or in its "Related" list.

| Operation | Commands covered | Impact | Risks |
|---|---|---|---|
| [Pre-execution checklist](pre-execution-checklist.md) | `kolla-ansible genconfig`<br>`docker exec -u root <c> /usr/local/bin/kolla_set_configs --check`<br>`kolla-ansible pull`<br>`kolla-ansible mariadb_backup`<br>`kolla-ansible prechecks` (first 2024.1 run)<br>and the `openstack` checks of its steps 5 and 6 | `writes-config` | – |
| [Predict and inspect a run](predict-a-run.md) | `EXTRA_OPTS="--list-tags" kolla-ansible -i multinode deploy`<br>`EXTRA_OPTS="--list-hosts" kolla-ansible -i multinode -t nova reconfigure`<br>`EXTRA_OPTS="--list-tasks" …`<br>`kolla-ansible -i multinode genconfig [-t <svc>] [--limit <hosts>]`<br>`docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?` (Podman: `podman exec -u root …`)<br>`EXTRA_OPTS="--check --diff" kolla-ansible … reconfigure`<br>`kolla-ansible -i multinode prechecks [-t <svc>]` | `read-only`, `writes-config` | – |
| [Reconfigure a single service](reconfigure-a-service.md) | `kolla-ansible -i multinode -t keystone reconfigure`<br>`kolla-ansible -i multinode -t nova --skip-tags haproxy reconfigure` | `restarts-on-drift` | [R8](../risk/risk-register.md#r8), [R14](../risk/risk-register.md#r14), [R19](../risk/risk-register.md#r19), [R20](../risk/risk-register.md#r20), [R23](../risk/risk-register.md#r23), [R24](../risk/risk-register.md#r24) |
| [Reconfigure Nova](reconfigure-nova.md) | `kolla-ansible -i multinode -t nova reconfigure`<br>`kolla-ansible -i multinode -t nova-api reconfigure`<br>`kolla-ansible -i multinode -t nova-cell reconfigure` | `restarts-on-drift` | [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2), [R3](../risk/risk-register.md#r3), [R24](../risk/risk-register.md#r24) |
| [Reconfigure Neutron](reconfigure-neutron.md) | `kolla-ansible -i multinode -t neutron reconfigure`<br>`kolla-ansible -i multinode -t neutron reconfigure --limit network01`<br>`kolla-ansible -i multinode -t openvswitch reconfigure --limit compute042` | `restarts-on-drift`, `critical` | [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7) |
| [Apply `common` changes (fluentd, cron, kolla_toolbox)](apply-common-changes.md) | `kolla-ansible -i multinode -t common reconfigure`<br>`kolla-ansible -i multinode -t common reconfigure --limit 'compute[0:49]'` | `restarts-on-drift` | [R2](../risk/risk-register.md#r2), [R25](../risk/risk-register.md#r25) |
| [Write config first, apply in controlled batches](controlled-batches.md) | `kolla-ansible -i multinode -t nova-cell genconfig`<br>`kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[0:9]'`<br>`kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[10:19]'`<br>`ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure`<br>`ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure -e kolla_max_fail_percentage=0` | `writes-config`, `restarts-on-drift` | [R1](../risk/risk-register.md#r1) |
| [Update container images](update-container-images.md) | `kolla-ansible -i multinode pull`<br>`kolla-ansible -i multinode -t nova pull --limit compute`<br>`kolla-ansible -i multinode upgrade`<br>`ANSIBLE_SERIAL=20 kolla-ansible -i multinode -t nova upgrade`<br>`kolla-ansible -i multinode prune-images --yes-i-really-really-mean-it` | `pulls-images`, `recreates-containers`, `critical` | [R7](../risk/risk-register.md#r7), [R11](../risk/risk-register.md#r11), [R12](../risk/risk-register.md#r12), [R13](../risk/risk-register.md#r13), [R17](../risk/risk-register.md#r17) |
| [Add a compute node](add-a-compute-node.md) | `kolla-ansible -i multinode bootstrap-servers --limit compute501`<br>`kolla-ansible -i multinode pull --limit compute501`<br>`kolla-ansible -i multinode deploy --limit compute501` | – | [R14](../risk/risk-register.md#r14), [R23](../risk/risk-register.md#r23) |
| [Change control-plane membership](change-control-plane-membership.md) | no command line in its command section; its scenario reads `-t nova,neutron reconfigure` | `restarts-on-drift`, `maintenance-window` | [R3](../risk/risk-register.md#r3), [R4](../risk/risk-register.md#r4) |
| [Database operations](database-operations.md) | `kolla-ansible -i multinode mariadb_backup`<br>`kolla-ansible -i multinode mariadb_recovery` | `recovery` | [R15](../risk/risk-register.md#r15), [R18](../risk/risk-register.md#r18) |
| [Stop and destroy](stop-and-destroy.md) | `kolla-ansible -i multinode stop --yes-i-really-really-mean-it -t heat --limit control03`<br>`kolla-ansible -i multinode destroy --yes-i-really-really-mean-it` | `critical` | [R15](../risk/risk-register.md#r15), [R16](../risk/risk-register.md#r16) |
| [Command quick lookup by tag](command-quick-lookup.md) | `-t <tag> reconfigure` for 15 tags (new rows: `letsencrypt`, `etcd`)<br>`reconfigure` (no tag)<br>`deploy-containers -t X`<br>`genconfig -t X`<br>`pull -t X` | `restarts-on-drift`, `writes-config`, `pulls-images` | by tag, in the "Risks" bullet of the [component pages](../components/index.md) |

## Assumed deployment

Every scenario assumes the same deployed state: 3 controllers, 2 network nodes, 3 computes, 1 storage node and 1
monitoring node, with Keystone, Glance, Placement, Nova, Neutron/OVS, Cinder/LVM, Heat and Horizon. The container engine
is Docker, the 2024.1 default (`kolla_container_engine: "docker"`, `group_vars/all.yml:92`) [CODE]; where a page
describes the Podman path, it says so.

## Conventions used by the command sections

These two lists apply to the command sections of every operation page and to the [Command quick lookup by
tag](command-quick-lookup.md).

The examples assume:

- the inventory is `/etc/kolla/multinode` (adapt `-i`);
- `globals.yml` and `passwords.yml` are in `/etc/kolla`;
- Ansible is ansible-core 2.16 (`tools/kolla-ansible:10-11` accepts 2.15 to 2.16; only 2.16.20 was read).

Conventions:

- **Scope** = plays and hosts touched.
- **Restarts** = containers that *can* restart (only if drift is detected).
- **One-shot** = bootstrap containers that run regardless of drift.

## Drift

Drift means what `compare_container` detects: a missing container, a changed image or container parameter (16
comparisons), `kolla_set_configs --check` reporting a change, or a systemd unit file whose text differs from the
rendered template (`module_utils/kolla_container_worker.py:58-65`, `module_utils/kolla_container_worker.py:67-89`)
[CODE]. The check reads `kolla_set_configs --check` per engine. With Docker, exit code 1 or 137, or a client error from
the exec, is drift (`module_utils/kolla_docker_worker.py:146-181`). With Podman, new in 2024.1, a container that is not
running is drift, 1 is drift, and any other non-zero code fails the task (`module_utils/kolla_podman_worker.py:428-453`)
([Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)). The
unit-file comparison is what makes the first 2024.1 check report drift for a container whose unit 2023.1 wrote
([F16](../reference/findings.md#f16)).

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
that establishes it:

1. **Config drift ⇒ full container stop/start.** It is never a reload. Still holds in 2024.1: the stop timeout is
   `docker_graceful_timeout`, **60 s** by default (`group_vars/all.yml:139`), passed to the module as
   `graceful_timeout` in `docker_common_options` (`group_vars/all.yml:151`). Each container runs under a
   `kolla-<name>-container.service` systemd unit, and a restart goes through that unit
   (`module_utils/kolla_docker_worker.py:439-459`,
   `module_utils/kolla_podman_worker.py:602-617`, `module_utils/kolla_systemd_worker.py:106-113`). Changed in 2024.1:
   the unit names the engine, `ExecStop=/usr/bin/${engine} stop ${name} -t ${graceful_timeout}`
   (`module_utils/kolla_systemd_worker.py:32`) ([Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)).
2. **Loop-notify.** One changed container in a role's loop restarts *every* container of that role on that host ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
3. **Global inputs.** `enable_*` flags, group membership and passwords are rendered into per-host files on every host
   ([Component dependencies §5](../components/dependencies.md#5-compute-node-dependency-summary)).

## Related

- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) (what each tag executes)
- [Risk register](../risk/risk-register.md) (risks [R1–R30](../risk/risk-register.md#r1))
- [Technical findings](../reference/findings.md) (the 2024.1 findings [F16](../reference/findings.md#f16) and
  [F17](../reference/findings.md#f17) behind the first 2024.1 run)
- [Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special) (nova-libvirt restarts)
- [Tag index](../risk/tag-index.md) and [What is not known](../troubleshooting/what-is-not-known.md) (tag index,
  everything marked [NOT AVAILABLE])
- [Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook) (the CLI →
  playbook mapping and the `kolla_serial` pass-through rules)
- [Tags](../risk/tags.md) (tag semantics)
- [Conventions and evidence labels](../start/conventions.md#evidence-labels) (evidence labels)
