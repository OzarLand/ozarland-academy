---
title: Tag index
description: From each Kolla-Ansible tag to its component page, with the full row kept for the tags that have no component page.
tags: [tags, risk, bootstrap-servers]
---

# Tag index

One row per tag. A tag that has a component page points to the "Where to look" section of that page, which says where
[Tags](tags.md) says what the tag executes and names the [Operations](../operations/index.md) scenario and command that
cover it and its [Risk register](risk-register.md) risks; the last column links to its service card. The three rows
without a component page (*(no tag)*, `service-rabbitmq` and `baremetal`) are kept in full. The [Tags](tags.md) tables
have one row per tag; the row to read is named after the link. Risk numbers link to the risk's own section of the [Risk
register](risk-register.md).

| Tag | What it executes ([Tags](tags.md)) | Scenario ([Operations](../operations/index.md)) | Command ([Operations](../operations/index.md)) | Risks ([Risk register](risk-register.md)) | Service card |
|---|---|---|---|---|---|
| *(no tag)* | [Tags §3](tags.md#3-what-a-tag-really-executes-master-table), row *(no tag)* | [Apply `common` changes (fluentd, cron, kolla_toolbox) §3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts) (`common` on all hosts), [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code) (new `openstack_tag` and `deploy`) | [Command quick lookup by tag](../operations/command-quick-lookup.md), row `reconfigure` (no tag) | [R2](risk-register.md#r2), [R12](risk-register.md#r12) | – |
| `common` (its own play in 2023.1, `site.yml:86-97`) | → [Common: fluentd, cron, kolla_toolbox](../components/common.md#where-to-look) | | | | [Fluentd / cron / kolla-toolbox](../components/common.md#service-card) |
| `nova` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (API level)](../components/nova.md#nova-api-level--role-nova), [Nova (cell level)](../components/nova.md#nova-cell-level--role-nova-cell) |
| `nova-api` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (API level)](../components/nova.md#nova-api-level--role-nova) |
| `nova-cell` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (cell level)](../components/nova.md#nova-cell-level--role-nova-cell) |
| `nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-` variants) and `nova-refresh-scheduler-cell-cache` | → [Nova](../components/nova.md#where-to-look) | | | | [Nova (API level)](../components/nova.md#nova-api-level--role-nova), [Nova (cell level)](../components/nova.md#nova-cell-level--role-nova-cell) |
| `neutron` | → [Neutron](../components/neutron.md#where-to-look) | | | | [Neutron](../components/neutron.md#service-card) |
| `openvswitch` | → [Open vSwitch](../components/openvswitch.md#where-to-look) | | | | [Open vSwitch](../components/openvswitch.md#service-card) |
| `ovn` (also `ovn-controller`, `ovn-db`) | → [OVN](../components/ovn.md#where-to-look) | | | | [OVN](../components/ovn.md#service-card) |
| `haproxy` (also `keepalived`, `loadbalancer`: the same loadbalancer play, `site.yml:99-108`) | → [HAProxy + Keepalived](../components/haproxy-keepalived.md#where-to-look) | | | | [HAProxy + Keepalived](../components/haproxy-keepalived.md#service-card) |
| `keystone` | → [Keystone](../components/keystone.md#where-to-look) | | | | [Keystone](../components/keystone.md#service-card) |
| `glance` | → [Glance](../components/glance.md#where-to-look) | | | | [Glance](../components/glance.md#service-card) |
| `cinder` | → [Cinder](../components/cinder.md#where-to-look) | | | | [Cinder](../components/cinder.md#service-card) |
| `heat` | → [Heat](../components/heat.md#where-to-look) | | | | [Heat](../components/heat.md#service-card) |
| `placement` | → [Placement](../components/placement.md#where-to-look) | | | | [Placement](../components/placement.md#service-card) |
| `horizon` | → [Horizon](../components/horizon.md#where-to-look) | | | | [Horizon](../components/horizon.md#service-card) |
| `mariadb` | → [MariaDB/Galera](../components/mariadb.md#where-to-look) | | | | [MariaDB/Galera](../components/mariadb.md#service-card) |
| `rabbitmq` | → [RabbitMQ](../components/rabbitmq.md#where-to-look) | | | | [RabbitMQ](../components/rabbitmq.md#service-card) |
| `memcached` / `memcache` | → [Memcached](../components/memcached.md#where-to-look) | | | | [Memcached](../components/memcached.md#service-card) |
| `chrony` (no play in 2023.1 `site.yml`: selects nothing) | → [Chrony](../components/chrony.md#where-to-look) | | | | [Chrony](../components/chrony.md#service-card) |
| `iscsi` | → [iscsid / tgtd](../components/iscsi.md#where-to-look) | | | | [iscsid / tgtd](../components/iscsi.md#service-card) |
| `service-rabbitmq` | [Tags §3](tags.md#3-what-a-tag-really-executes-master-table), row `service-rabbitmq` (not usable as a selector) | – | – | – | – |
| `baremetal` (`bootstrap-servers`) | [Tags §3](tags.md#3-what-a-tag-really-executes-master-table) and [Tags §3.1](tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `baremetal` | [Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node) | [Add a compute node §1.1](../operations/add-a-compute-node.md#11-add-a-compute-node) | [R14](risk-register.md#r14) | – |

Which tags reach the compute hosts is the "Target hosts" column of [Tags
§3](tags.md#3-what-a-tag-really-executes-master-table). Handlers are never filtered by tags ([Tags
§2.2](tags.md#22-handlers-ignore-tags-code)), and a tag never restricts which hosts a play targets ([Tags
§4](tags.md#4-practical-consequences)).

## Related

- [What a tag really executes](tags.md) — the master table and the per-tag answers
- [Components](../components/index.md) — the component pages that the rows point to
- [Command quick lookup by tag](../operations/command-quick-lookup.md) — per tag: hosts touched, containers that can
  restart and one-shot containers
- [Risk register](risk-register.md) — the risks [R1–R25](risk-register.md#r1)
- [Glossary](../reference/glossary.md) — the terms the study uses
