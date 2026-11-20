---
title: Chrony
description: Chrony in 2024.1 - still no chrony role, play, group or image; host time sync is the operator's job and is only checked by the prechecks.
tags: [chrony, fluentd, cron, kolla-toolbox, tags, risk, dependencies, unknowns]
---

# Chrony

This page was the starting point for chrony, the `chrony` role of Ussuri. **2024.1 has no chrony role**, as 2023.1 had
none [CODE]: `ansible/roles/` has no `chrony` directory (none of its 71 roles mentions chrony outside the prechecks),
`site.yml` has no chrony play (its first service play is "Apply role common", `site.yml:88-103`), `inventory/multinode`
has no `chrony` or `chrony-server` group, and kolla 2024.1 has no `docker/chrony` image. Kolla-Ansible does not deploy
a time service. Time sync is left to the host, and the only code that deals with it is a precheck ([Before and after a
run](#before-and-after-a-run)), unchanged since 2023.1. The page keeps its sections so that links to it still resolve;
each says what applies in 2024.1.

## Where to look

### Operate

- **Scenario:** none for chrony in 2024.1. `common` changes are pushed with `-t common` ([Apply `common` changes
  (fluentd, cron, kolla_toolbox) §3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts)): the
  common play is tagged `common` only (`site.yml:100-101`).
- **Command:** [Apply `common` changes (fluentd, cron, kolla_toolbox)
  §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox):
  `kolla-ansible -i multinode -t common reconfigure`.
- [Command quick lookup by tag](../operations/command-quick-lookup.md), row `-t chrony reconfigure`: no `chrony` role or
  play in 2024.1; only the `always`-tagged plays run (fact gathering, `site.yml:2` and `gather-facts.yml:26`, `:62`;
  host grouping, `site.yml:7-75`) [CODE].
- Host time sync itself is checked by `kolla-ansible prechecks` (`tools/kolla-ansible:444-446` sets
  `kolla_action=precheck`; the prechecks play runs on the group `kolla_action_precheck`, `site.yml:77-86`) [CODE].

### Impact and risk

- **What the tag executes (`chrony`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `chrony`:
  nothing besides the `always` plays.
- **Risks:** [R2](../risk/risk-register.md#r2) and [R25](../risk/risk-register.md#r25) do not involve chrony: the
  `common` play is reached with `-t common` or an untagged run (`site.yml:88-103`).

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components) (row "Chrony"),
  [Component dependencies §5](dependencies.md#5-compute-node-dependency-summary): no chrony container and no
  `chrony.conf` on any host, so the internal VIP and `external_ntp_servers` are not inputs of a compute host's
  configuration [CODE]: `ansible/` has no reference to `external_ntp_servers`, and none to `chrony` outside
  `roles/prechecks/tasks/timesync_checks.yml`. The only other NTP setting is the per-range `ntp_server` DHCP option of
  Ironic's dnsmasq (`roles/ironic/templates/ironic-dnsmasq.conf.j2:13`), which is handed to the bare-metal nodes Ironic
  provisions, not to the Kolla hosts.

### Evidence

- **Fact sheet:** [fact sheet A §4](../reference/factsheets/a-infra-lb-ovn.md#4-chrony-role) describes the Ussuri role.
- **Code for 2024.1:** `roles/prechecks/tasks/timesync_checks.yml:1-47` (host NTP daemon and clock checks),
  `roles/prechecks/tasks/main.yml:7-9` (where they run), `roles/prechecks/defaults/main.yml:5-6` (the switch). **Still
  holds in 2024.1** [CODE]: `timesync_checks.yml` and `datetime_checks.yml` are identical to their 2023.1 versions.
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour): no chrony image in kolla
  2024.1.
- **Host side:** ansible-collection-kolla 2024.1 (`bootstrap-servers`) neither installs nor configures an NTP daemon
  (no `chrony`, `ntp` or `timesync` in its `roles/`; its package lists are `roles/packages/defaults/main.yml:10-34`),
  and does not remove the host `chrony` package ([R14](../risk/risk-register.md#r14)) [CODE].

### Before and after a run

- `kolla-ansible prechecks`, on every host except those of the `deployment` group (`roles/prechecks/tasks/main.yml:7-9`)
  and only while `prechecks_enable_host_ntp_checks` is true (the default, `roles/prechecks/defaults/main.yml:6`;
  `roles/prechecks/tasks/timesync_checks.yml:47`) [CODE]:
  1. `systemctl is-active chrony chronyd ntp ntpd systemd-timesyncd`; fails with "No host NTP daemon is running" when
     the command's return code is not 0 (`timesync_checks.yml:3-28`);
  2. `timedatectl status`; fails when its output lacks `synchronized: yes` (`timesync_checks.yml:30-46`).
- `roles/prechecks/tasks/datetime_checks.yml:1-26` also fails when `/etc/localtime` is missing (all hosts) or
  `/etc/timezone` is missing (Debian family): both are bind-mounted into the containers (e.g.
  `roles/iscsi/defaults/main.yml:43-44`) [CODE]. It is imported for every host the prechecks play runs on
  (`roles/prechecks/tasks/main.yml:11`), the `deployment` group included.
- Set `prechecks_enable_host_ntp_checks: false` only when the host runs a daemon the check does not know, or one
  `timedatectl` does not recognise (the messages at `timesync_checks.yml:21-26`, `:39-44`).
- The prechecks play runs only when `kolla_action` is `precheck` (`site.yml:77-86`): `deploy`, `reconfigure` and
  `upgrade` do not run these checks [CODE].

### Known limits and open points

- The fact sheet items on the Ussuri role ([fact sheet A
  §4.7](../reference/factsheets/a-infra-lb-ovn.md#47-dependencies),
  [§4.8](../reference/factsheets/a-infra-lb-ovn.md#48-operationally-notable); [fact sheet D
  §5.12](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#512-chrony)): the VIP as internal time
  source, `ip_nonlocal_bind` on the chrony servers, the public pool default, a chrony restart stepping the clock. None
  of them applies to 2024.1: there is no chrony container, configuration or VIP time source to restart or reconfigure.
- [NOT AVAILABLE] Which time source the hosts use, and how the operator configures it: the host NTP daemon is outside
  the Kolla-Ansible code. The precheck only proves that one of five daemons is active and that `timedatectl` reports a
  synchronised clock at precheck time; no deploy or reconfigure task checks it again.
- [NOT AVAILABLE] What happens to a `chrony` container left on a host from an earlier release: no 2024.1 task stops,
  removes or checks it (no `chrony` reference in `ansible/` outside the precheck that looks at host services).
- [R14](../risk/risk-register.md#r14): a `bootstrap-servers` re-run on a live host still removes host packages
  (`open-iscsi`, `libvirt*`, …), but `chrony` is not among them (ansible-collection-kolla
  `roles/packages/defaults/main.yml:25-34`, removed by `roles/packages/tasks/main.yml:15-23`) [CODE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), [Open
  questions](../troubleshooting/open-questions.md) and [Findings](../reference/findings.md) have no entry on chrony.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- Service card removed: there is no chrony role in 2024.1. -->

## Related

- [Apply `common` changes (fluentd, cron, kolla_toolbox)](../operations/apply-common-changes.md) — `-t common
  reconfigure`, the command that pushes `common` changes (there is no `-t chrony` play)
- [Common: fluentd, cron, kolla_toolbox](common.md) — the `common` role and its own play
- [HAProxy + Keepalived](haproxy-keepalived.md) — the loadbalancer role; the VIP is not a time source
- [Component dependencies §5](dependencies.md#5-compute-node-dependency-summary) — the global inputs of a compute host
- [Components](index.md) — the other component pages
