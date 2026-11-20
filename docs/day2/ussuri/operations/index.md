---
title: Operations
description: Catalogue of the Day-2 operation pages with their commands, impact classes and risks, and the assumptions and conventions they share.
tags: [reconfigure, deploy, upgrade, genconfig, deploy-containers, pull, loop-notify, limit, risk]
---

# Operations

What Kolla-Ansible Ussuri commands do when they run against a live platform, read from the source of the **unmodified
`site.yml`**, its roles and Ansible 2.9.27. Nothing was run against a host.

Real `kolla-ansible` (Ussuri) invocations with what they select, their scope and their impact.

> [!NOTE]
> **Key answers**
>
> - **A service tag also touches** the HAProxy frontends of the service, `common` on every host of the service play,
>   Keystone registration, for most services DB creation and schema sync (Neutron's DB sync only on `deploy` by
>   default), and hosts outside `--limit` ([Reconfigure a single service
>   §2](reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects)). A controller membership change is
>   a fleet-wide restart event for every messaging consumer ([Change control-plane membership
>   §2](change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)); what adding a
>   compute with `deploy --limit` touches: [Add a compute node §2](add-a-compute-node.md#2-add-a-compute-node).
> - **Recommended pattern:** `genconfig`, then `deploy-containers --limit` batch by batch, with its caveats [CODE]
>   ([Write config first, apply in controlled batches
>   §2](controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)). Why a small change can create a
>   large workload: [Why a small change creates a large workload](../risk/small-change-large-workload.md).
> - **Leave HAProxy alone:** `--skip-tags haproxy` ([Reconfigure a single service
>   §1.2](reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)). **Push `common` changes:**
>   `-t chrony`, because `-t common` is a no-op ([Apply `common` changes (fluentd, cron, kolla_toolbox)
>   §1.1](apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)).
> - **Add a compute:** `bootstrap-servers`, `pull` and `deploy`, each with `--limit` ([Add a compute node
>   §1.1](add-a-compute-node.md#11-add-a-compute-node)). **Per-tag quick lookup** of hosts touched, possible restarts
>   and one-shot containers: [Command quick lookup by tag](command-quick-lookup.md).

## Operations catalogue

One row per operation page, in the order of the navigation. The commands are copied from each page. The impact classes
are defined in [Operation impact classes](../start/conventions.md#operation-impact-classes). The risk numbers are those
the page cites, in its text or in its "Related" list.

| Operation | Commands covered | Impact | Risks |
|---|---|---|---|
| [Pre-execution checklist](pre-execution-checklist.md) | `kolla-ansible genconfig`<br>`docker exec -u root <c> /usr/local/bin/kolla_set_configs --check`<br>`kolla-ansible pull`<br>`kolla-ansible mariadb_backup`<br>and the `openstack` checks of its steps 5 and 6 | `writes-config` | – |
| [Predict and inspect a run](predict-a-run.md) | `EXTRA_OPTS="--list-tags" kolla-ansible -i multinode deploy`<br>`EXTRA_OPTS="--list-hosts" kolla-ansible -i multinode -t nova reconfigure`<br>`EXTRA_OPTS="--list-tasks" …`<br>`kolla-ansible -i multinode genconfig [-t <svc>] [--limit <hosts>]`<br>`docker exec -u root <container> /usr/local/bin/kolla_set_configs --check; echo $?`<br>`EXTRA_OPTS="--check --diff" kolla-ansible … reconfigure`<br>`kolla-ansible -i multinode prechecks [-t <svc>]` | `read-only`, `writes-config` | – |
| [Reconfigure a single service](reconfigure-a-service.md) | `kolla-ansible -i multinode -t keystone reconfigure`<br>`kolla-ansible -i multinode -t nova --skip-tags haproxy reconfigure` | `restarts-on-drift` | [R8](../risk/risk-register.md#r8), [R19](../risk/risk-register.md#r19), [R20](../risk/risk-register.md#r20), [R23](../risk/risk-register.md#r23), [R24](../risk/risk-register.md#r24) |
| [Reconfigure Nova](reconfigure-nova.md) | `kolla-ansible -i multinode -t nova reconfigure`<br>`kolla-ansible -i multinode -t nova-api reconfigure`<br>`kolla-ansible -i multinode -t nova-cell reconfigure` | `restarts-on-drift` | [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2), [R3](../risk/risk-register.md#r3), [R24](../risk/risk-register.md#r24) |
| [Reconfigure Neutron](reconfigure-neutron.md) | `kolla-ansible -i multinode -t neutron reconfigure`<br>`kolla-ansible -i multinode -t neutron reconfigure --limit network01`<br>`kolla-ansible -i multinode -t openvswitch reconfigure --limit compute042` | `restarts-on-drift`, `critical` | [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7) |
| [Apply `common` changes (fluentd, cron, kolla_toolbox)](apply-common-changes.md) | `kolla-ansible -i multinode -t chrony reconfigure`<br>`kolla-ansible -i multinode -t chrony reconfigure --limit 'compute[0:49]'` | `restarts-on-drift` | [R2](../risk/risk-register.md#r2), [R25](../risk/risk-register.md#r25) |
| [Write config first, apply in controlled batches](controlled-batches.md) | `kolla-ansible -i multinode -t nova-cell genconfig`<br>`kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[0:9]'`<br>`kolla-ansible -i multinode -t nova-cell deploy-containers --limit 'compute[10:19]'`<br>`ANSIBLE_SERIAL=10 kolla-ansible -i multinode -t nova reconfigure` | `writes-config`, `restarts-on-drift` | [R1](../risk/risk-register.md#r1) |
| [Update container images](update-container-images.md) | `kolla-ansible -i multinode pull`<br>`kolla-ansible -i multinode -t nova pull --limit compute`<br>`kolla-ansible -i multinode upgrade`<br>`ANSIBLE_SERIAL=20 kolla-ansible -i multinode -t nova upgrade` | `pulls-images`, `recreates-containers`, `critical` | [R7](../risk/risk-register.md#r7), [R11](../risk/risk-register.md#r11), [R12](../risk/risk-register.md#r12), [R13](../risk/risk-register.md#r13) |
| [Add a compute node](add-a-compute-node.md) | `kolla-ansible -i multinode bootstrap-servers --limit compute501`<br>`kolla-ansible -i multinode pull --limit compute501`<br>`kolla-ansible -i multinode deploy --limit compute501` | – | [R14](../risk/risk-register.md#r14), [R23](../risk/risk-register.md#r23) |
| [Change control-plane membership](change-control-plane-membership.md) | no command line in its command section; its scenario reads `-t nova,neutron reconfigure` | `restarts-on-drift`, `maintenance-window` | [R3](../risk/risk-register.md#r3), [R4](../risk/risk-register.md#r4) |
| [Database operations](database-operations.md) | `kolla-ansible -i multinode mariadb_backup`<br>`kolla-ansible -i multinode mariadb_recovery` | `recovery` | [R18](../risk/risk-register.md#r18) |
| [Stop and destroy](stop-and-destroy.md) | `kolla-ansible -i multinode stop --yes-i-really-really-mean-it -t heat --limit control03`<br>`kolla-ansible -i multinode destroy --yes-i-really-really-mean-it` | `critical` | [R15](../risk/risk-register.md#r15), [R16](../risk/risk-register.md#r16) |
| [Command quick lookup by tag](command-quick-lookup.md) | `-t <tag> reconfigure` for 12 tags<br>`reconfigure` (no tag)<br>`deploy-containers -t X`<br>`genconfig -t X`<br>`pull -t X` | `restarts-on-drift`, `writes-config`, `pulls-images` | by tag, in the "Risks" bullet of the [component pages](../components/index.md) |

## Assumed deployment

Every scenario assumes the same deployed state: 3 controllers, 2 network nodes, 3 computes, 1 storage node and 1
monitoring node, with Keystone, Glance, Placement, Nova, Neutron/OVS, Cinder/LVM, Heat and Horizon.

## Conventions used by the command sections

These two lists apply to the command sections of every operation page and to the [Command quick lookup by
tag](command-quick-lookup.md).

The examples assume:

- the inventory is `/etc/kolla/multinode` (adapt `-i`);
- `globals.yml` and `passwords.yml` are in `/etc/kolla`;
- Ansible is 2.9.

Conventions:

- **Scope** = plays and hosts touched.
- **Restarts** = containers that *can* restart (only if drift is detected).
- **One-shot** = bootstrap containers that run regardless of drift.

## Drift

Drift means what `compare_container` detects: a changed image or container parameter, or `kolla_set_configs --check`
exiting 1 (`library/kolla_docker.py:326-332`; [Kolla images
§3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes)).

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

1. **Config drift ⇒ full container stop/start.** It is never a reload. The stop timeout is effectively **10 s**
   ([Repository architecture
   §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)).
2. **Loop-notify.** One changed container in a role's loop restarts *every* container of that role on that host ([Tags
   §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
3. **Global inputs.** `enable_*` flags, group membership and passwords are rendered into per-host files on every host
   ([Component dependencies §5](../components/dependencies.md#5-compute-node-dependency-summary)).

## Related

- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) (what each tag executes)
- [Risk register](../risk/risk-register.md) (risks [R1–R25](../risk/risk-register.md#r1))
- [Nova deep dive §5](../components/nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special) (nova-libvirt restarts)
- [Tag index](../risk/tag-index.md) and [What is not known](../troubleshooting/what-is-not-known.md) (tag index,
  everything marked [NOT AVAILABLE])
- [Repository architecture §2](../concepts/repository-architecture.md#2-from-cli-to-ansible-playbook) (the CLI →
  playbook mapping and the `kolla_serial` pass-through rules)
- [Tags](../risk/tags.md) (tag semantics)
- [Conventions and evidence labels](../start/conventions.md#evidence-labels) (evidence labels)
