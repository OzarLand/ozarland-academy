---
title: Chrony
description: Where the study covers chrony (role chrony), whose play reaches every host with the default inventory and so serves to push common changes, and its open points.
tags: [chrony, fluentd, cron, kolla-toolbox, tags, risk, dependencies, unknowns]
---

# Chrony

This page is the starting point for chrony, the `chrony` role: one container, `chrony`, on the compute, control,
monitoring, network and storage nodes of the example inventory, selected by the tag `chrony`. Its play is the first play
for every host ([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row `chrony`), and `-t chrony` is
the recommended way to push `common` changes ([Apply `common` changes (fluentd, cron, kolla_toolbox)
§3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts)). The lists below say where the study
covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open;
the service card follows them.

## Where to look

### Operate

- **Scenario:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts) (the way to push `common` changes)
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox)
- [Command quick lookup by tag](../operations/command-quick-lookup.md), row `-t chrony reconfigure`: hosts touched with
  the default inventory: all hosts; can restart, only if drift is detected: chrony + common (fluentd, cron, toolbox);
  typical duration driver: the number of hosts.

### Impact and risk

- **What the tag executes (`chrony`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `chrony`
- **Risks:** through `common`: [R2](../risk/risk-register.md#r2), [R25](../risk/risk-register.md#r25)

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §5](dependencies.md#5-compute-node-dependency-summary)

### Evidence

- **Fact sheet:** [fact sheet A §4](../reference/factsheets/a-infra-lb-ovn.md#4-chrony-role)
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (row `chrony`)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `chrony`:
  safe on its own "yes; also the cheapest way to push common config fleet-wide"; prerequisite: VIP up for the chrony
  clients.
- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row `chrony`: the containers that can restart,
  only if a change is detected, are chrony, fluentd, cron and kolla_toolbox.
- [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox):
  `-t chrony reconfigure` also reconfigures chrony on those hosts. If `enable_chrony` is `no`, use any service tag whose
  play covers the hosts, e.g. `-t openvswitch` for network and compute hosts.
- [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §4](../operations/apply-common-changes.md#4-sequence-risks-and-verification): the verification before and after, for
  `fluentd`, `cron` and `kolla_toolbox`.

### Known limits and open points

- [fact sheet A §4.8](../reference/factsheets/a-infra-lb-ovn.md#48-operationally-notable), "Operationally notable", four
  items: low data-plane risk (NOT AVAILABLE: whether a restart steps the clock); cost scales with the number of hosts;
  chrony.conf depends on the haproxy group; the VIP is the internal time source (NOT AVAILABLE: whether reachable
  external NTP servers mitigate the change of clock source when the VIP fails over).
- [fact sheet A §4.7](../reference/factsheets/a-infra-lb-ovn.md#47-dependencies): NOT AVAILABLE: whether, on a first
  deploy, chronyd on a non-VIP chrony-server host can bind the VIP before `ip_nonlocal_bind` is set, and whether it then
  serves before a later restart.
- [fact sheet D §5.12](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#512-chrony): by default
  every compute queries public pool servers. NOT AVAILABLE: whether a chrony restart (image or config change) on a
  drifted compute steps the clock by more than 3 s in the first updates.
- [R14](../risk/risk-register.md#r14): a `bootstrap-servers` re-run on a live host removes host packages (`open-iscsi`,
  `libvirt*`, `chrony`, …).
- [What is not known](../troubleshooting/what-is-not-known.md#in-the-fact-sheets): the fact sheets mark their own
  NOT AVAILABLE points inline; the table lists fact sheet A §4.7 and §4.8 and fact sheet D §5.12 among the sections that
  contain such marks.
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on chrony.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py chrony -->

| Item | Value |
|---|---|
| Play | site.yml:114 |
| Tags | chrony |
| Play host patterns | chrony-server, chrony |
| Node types in play (example inventory) | compute, control, monitoring, network, storage |
| Node types running its containers | compute, control, monitoring, network, storage |
| Containers | `chrony` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → flush handlers |
| Task files | check-containers.yml, check.yml, config.yml, deploy-containers.yml, deploy.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `chrony.conf.j2`, `chrony.json.j2` |
| Handlers (definition order) | Restart chrony container |
| Key variables | `enable_chrony`, `external_ntp_servers` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md) —
  `-t chrony reconfigure`, the command that pushes `common` changes
- [Common: fluentd, cron, kolla_toolbox](common.md) — the containers that a `-t chrony` run also checks
- [HAProxy + Keepalived](haproxy-keepalived.md) — in the example inventory `chrony-server` is the haproxy group, and the
  VIP is the internal time source
- [Component dependencies §5](dependencies.md#5-compute-node-dependency-summary) — the global inputs of a compute's
  `chrony.conf`
- [Components](index.md) — the other component pages
