---
title: Components
description: One page per component of the 2024.1 study, with its role, tags, containers and node types, plus the pages on component dependencies and on Nova in depth.
tags: [keystone, glance, placement, nova, neutron, cinder, horizon, heat, barbican, octavia, swift, manila, mariadb, rabbitmq, memcached, haproxy, keepalived, loadbalancer, proxysql, letsencrypt, fluentd, cron, kolla-toolbox, openvswitch, ovn, chrony, iscsi, inventory, tags]
---

# Components

The entry point by component: twelve OpenStack services and nine infrastructure components, each with a page that says
where the study covers it and that ends with its service card. Two more pages cut across the components: [Component
dependencies](dependencies.md) and [Nova deep dive](nova-deep-dive.md).

One row per service card. The columns "Role and tag", "Containers" and "Runs on" restate the card; "Runs on" is the
card row "Node types running its containers", read with the 2024.1 example `multinode` inventory ([How to read a
service card](#how-to-read-a-service-card)). Two cards leave a row empty, and their rows below are read from the code
instead [CODE]:

- the MariaDB and RabbitMQ cards leave "Node types running its containers" empty: their containers are placed on a
  group named by a variable (`mariadb_shard_group`, `group_vars/all.yml:480`; `role_rabbitmq_groups`, set to
  `rabbitmq` at `rabbitmq.yml:21`). Their plays are in `mariadb.yml` and `rabbitmq.yml`, imported at `site.yml:400`
  and `site.yml:468`, and the `mariadb` and `rabbitmq` groups are children of `control` (`inventory/multinode:87-91`).

Chrony has no card: still no `chrony` role in 2024.1 (no `roles/chrony` directory, no chrony play in `site.yml`).

## OpenStack services

| Component | Role and tag | Containers | Runs on |
|---|---|---|---|
| [Keystone](keystone.md) | role `keystone`, tag `keystone` | `keystone`, `keystone_ssh`, `keystone_fernet` | control |
| [Glance](glance.md) | role `glance`, tag `glance` | `glance_api`, `glance_tls_proxy` | control |
| [Placement](placement.md) | role `placement`, tag `placement` | `placement_api` | control |
| [Nova](nova.md), API level | role `nova`, tags `nova`, `nova-api(-*)` | `nova_api`, `nova_scheduler`, `nova_super_conductor` | control |
| [Nova](nova.md), cell level | role `nova-cell`, tags `nova`, `nova-cell(-*)` | `nova_libvirt`, `nova_ssh`, `nova_novncproxy`, `nova_spicehtml5proxy`, `nova_serialproxy`, `nova_conductor`, `nova_compute`, `nova_compute_ironic` | compute, control |
| [Neutron](neutron.md) | role `neutron`, tag `neutron` | `neutron_server`, `neutron_openvswitch_agent`, `neutron_linuxbridge_agent`, `neutron_dhcp_agent`, `neutron_l3_agent`, `neutron_sriov_agent`, `neutron_mlnx_agent`, `neutron_eswitchd`, `neutron_metadata_agent`, `neutron_ovn_metadata_agent`, `neutron_bgp_dragent`, `neutron_infoblox_ipam_agent`, `neutron_metering_agent`, `ironic_neutron_agent`, `neutron_tls_proxy`, `neutron_ovn_agent` | compute, control, network |
| [Cinder](cinder.md) | role `cinder`, tag `cinder` | `cinder_api`, `cinder_scheduler`, `cinder_volume`, `cinder_backup` | control, storage |
| [Horizon](horizon.md) | role `horizon`, tag `horizon` | `horizon` | control |
| [Heat](heat.md) | role `heat`, tag `heat` | `heat_api`, `heat_api_cfn`, `heat_engine` | control |
| [Barbican](barbican.md) | role `barbican`, tag `barbican` | `barbican_api`, `barbican_keystone_listener`, `barbican_worker` | control |
| [Octavia](octavia.md) | role `octavia`, tag `octavia` | `octavia_api`, `octavia_driver_agent`, `octavia_health_manager`, `octavia_housekeeping`, `octavia_worker` | control |
| [Swift](swift.md) | role `swift`, tag `swift` | `swift_proxy_server`, `swift_rsyncd`, `swift_account_server`, `swift_account_auditor`, `swift_account_replication_server`, `swift_account_replicator`, `swift_account_reaper`, `swift_container_server`, `swift_container_auditor`, `swift_container_replication_server`, `swift_container_replicator`, `swift_container_updater`, `swift_object_server`, `swift_object_auditor`, `swift_object_replication_server`, `swift_object_replicator`, `swift_object_updater`, `swift_object_expirer` (from `roles/swift/tasks/start.yml`, see above) | control, storage |
| [Manila](manila.md) | role `manila`, tag `manila` | `manila_api`, `manila_scheduler`, `manila_share`, `manila_data` | control, network |

## Infrastructure and dependencies

| Component | Role and tag | Containers | Runs on |
|---|---|---|---|
| [MariaDB/Galera](mariadb.md) | role `mariadb`, tag `mariadb` (`mariadb.yml:3-16`, five plays) | `mariadb`, `mariadb_clustercheck` | control |
| [RabbitMQ](rabbitmq.md) | role `rabbitmq`, tag `rabbitmq` (`rabbitmq.yml:3-70`, three plays; the outward RabbitMQ plays of 2023.1 are gone) | `rabbitmq` | control |
| [Memcached](memcached.md) | role `memcached`, tags `memcache`, `memcached` | `memcached` | control |
| [HAProxy + Keepalived](haproxy-keepalived.md) | role `loadbalancer`, tags `haproxy`, `keepalived`, `loadbalancer`; each of the 39 per-service `include_role … tasks_from: loadbalancer` tasks in this play (44 in 2023.1) also carries its service tag | `haproxy`, `proxysql`, `keepalived`, `haproxy_ssh` (new in 2024.1, only with `enable_letsencrypt`) | network |
| [Common: fluentd, cron, kolla_toolbox](common.md) | role `common`, tag `common` (its own play, `site.yml:88-103`; no other play runs it) | `fluentd`, `kolla_toolbox`, `cron` | compute, control, monitoring, network, storage |
| [Open vSwitch](openvswitch.md) | role `openvswitch`, tag `openvswitch` | `openvswitch_db`, `openvswitch_vswitchd` | compute, network |
| [OVN](ovn.md) | roles `ovn-controller` (tags `ovn`, `ovn-controller`) and `ovn-db` (tags `ovn`, `ovn-db`) | `ovn_controller`, `ovn_northd`, `ovn_nb_db`, `ovn_sb_db` | compute, control, network |
| [Chrony](chrony.md) | none in 2024.1: no `roles/chrony`, no chrony play in `site.yml` | – | – |
| [iscsid / tgtd](iscsi.md) | role `iscsi`, tag `iscsi` | `iscsid`, `tgtd` | compute, control, storage |

## Across components

- [Component dependencies](dependencies.md) — what depends on what, in four kinds of dependency: installation,
  configuration, runtime and operational
- [Nova deep dive](nova-deep-dive.md) — Nova in depth: its two roles and ten plays, its dependencies, what restarts
  what, and the `nova_libvirt` restart

## Roles without a component page

Other roles: the roles that place containers on compute hosts (ceilometer, multipathd, collectd, telegraf, prometheus
exporters, masakari, zun, kuryr, cyborg; skydive, nova-hyperv and, new in 2024.1, monasca have no role at all) are in
[fact sheet D §5](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#50-summary-table-compute-side);
the new `letsencrypt` role (its own play, on the `letsencrypt` group, a child of `loadbalancer`: `site.yml:328-340`,
`inventory/multinode:192-193`) is in [fact sheet A](../reference/factsheets/a-infra-lb-ovn.md) and on the [HAProxy +
Keepalived](haproxy-keepalived.md) page; `bootstrap-servers` (the ansible-collection-kolla roles `baremetal`, `docker`
or, new in 2024.1, `podman`, chosen from `kolla_container_engine`, `etc_hosts`, …: ansible-collection-kolla
`roles/baremetal/defaults/main.yml:37`, `roles/baremetal/tasks/install.yml:38`) and the operational playbooks are in
[fact sheet E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md); every play, container, role and handler is
listed in [Generated inventory](../reference/generated-inventory.md). The roles removed in 2024.1 (freezer, kafka,
monasca, murano, sahara, senlin, solum, storm, vitrage, zookeeper) have no directory under `ansible/roles/` and no play.

## How to read a component page

Most component pages first say what changed in 2024.1 for the component. Every component page then has the same two
main parts: "Where to look", then the service card.

"Where to look" lists the sections of the study that cover the component, under these sub-headings when the study has
something to list:

- **Operate** — the scenario and the command lines;
- **Impact and risk** — what the tag executes, and the risks;
- **Dependencies** — the rows of [Component dependencies](dependencies.md);
- **Evidence** — the fact sheet, the image side, and "Also";
- **Before and after a run** — the checks, prerequisites and precautions the study gives;
- **Known limits and open points** — known bugs, open questions, findings, and what the sources do not establish.

"Fact sheet" is the per-role evidence; "–" means no fact sheet covers the role, and the "Also" bullet says where it is
traced instead.

## How to read a service card

For each core service: Kolla role, play in `site.yml`, tags, task flow for `deploy`/`reconfigure`, templates, handlers,
key variables, and the node types its play touches with the 2024.1 example `multinode` inventory. "Play hosts" = every
host matched by the play's host patterns (before `enable_*` filtering). "Container hosts" = hosts where at least one
container of the role is placed (group-based placement; `host_in_groups` expressions are summarised by their groups).

In the cards, "Play hosts" is the row "Node types in play (example inventory)" and "Container hosts" is the row "Node
types running its containers". There are 22 cards on 20 of the 21 component pages: the [Nova](nova.md) page has one for
the role `nova` and one for the role `nova-cell`, the [OVN](ovn.md) page one for `ovn-controller` and one for `ovn-db`,
and the [Chrony](chrony.md) page has none. The cards are generated from the 2024.1 tree by
[tools/service_cards.py](https://github.com/OzarLand/kolla-ansible-academy/blob/main/tools/service_cards.py); a row
the tool cannot resolve shows "–" (see the introduction for the three cards concerned).

## Related

- [Tag index](../risk/tag-index.md) — from a tag to its component page
- [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) — what each tag executes, on which hosts
- [Per-role fact sheets](../reference/factsheets/index.md) — the per-role evidence behind the component pages
- [Generated inventory](../reference/generated-inventory.md) — every play, container, role and handler
- [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) — what each image does on every start
- [Risk register](../risk/risk-register.md) — the 30 risks that the "Risks" bullets point to (R25 does not apply to
  2024.1)
