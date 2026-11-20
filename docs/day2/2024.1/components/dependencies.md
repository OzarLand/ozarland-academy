---
title: Component dependencies
description: What depends on what in Kolla-Ansible 2024.1, in four kinds of dependency, from the shared substrate and infrastructure to compute hosts and deployment order.
tags: [dependencies, haproxy, keepalived, mariadb, rabbitmq, memcached, etcd, redis, keystone, nova, neutron, openvswitch, ovn, chrony, iscsi, fluentd, kolla-toolbox]
remember:
  - "The database and etcd are reached through the internal VIP and HAProxy; RabbitMQ and memcached hosts are listed one by one in the configs of the services that use them (27 roles loop over <code>groups['memcached']</code>). <span class=\"ev ev-code\">CODE</span>"
  - "Adding or removing a RabbitMQ node changes the config of every messaging service, including <code>nova-compute</code> and the neutron agents on every compute; in 2024.1 the same configs also carry <code>rabbit_quorum_queue = true</code> by default. <span class=\"ev ev-code\">CODE</span>"
  - "A compute host's configuration depends on global state, not only on the host itself: that is why changes that look small trigger fleet-wide restarts. <span class=\"ev ev-code\">CODE</span>"
  - "HAProxy is restarted, never reloaded: on the backup hosts first, then on the host that holds the VIP. <span class=\"ev ev-code\">CODE</span>"
  - "Nova is deployed before Open vSwitch, OVN and Neutron, and nothing enforces a dependency when you use tags. <span class=\"ev ev-code\">CODE</span>"
quiz:
  - q: "How do OpenStack services reach RabbitMQ in 2024.1?"
    options: ["Through the internal VIP and HAProxy, like the database", "Every host of <code>groups['rabbitmq']</code> is listed directly in their configs"]
    answer: 1
    explain: "<code>rpc_transport_url</code> / <code>notify_transport_url</code> loop over every host of <code>groups['rabbitmq']</code>; clients use their own failover, not the VIP. Adding or removing a RabbitMQ node changes the config of every messaging service, including <code>nova-compute</code> and the neutron agents on every compute."
    see: "1-the-shared-substrate-what-every-openstack-service-uses"
  - q: "How does Cinder reach etcd when <code>cinder_coordination_backend</code> is <code>etcd</code>?"
    options: ["Through the internal VIP (<code>kolla_internal_fqdn</code>) and the etcd HAProxy frontend", "By listing every host of <code>groups['etcd']</code> in <code>cinder.conf</code>"]
    answer: 0
    explain: "The <code>[coordination]</code> <code>backend_url</code> points at <code>kolla_internal_fqdn:etcd_client_port</code>, and the etcd role defines an internal HAProxy frontend. No service template except Prometheus's loops over <code>groups['etcd']</code>, so an etcd membership change does not change compute configs."
    see: "1-the-shared-substrate-what-every-openstack-service-uses"
  - q: "How is HAProxy restarted when its configuration changes?"
    options: ["Restarted, never reloaded: on the backup hosts first, then on the host that holds the VIP", "Reloaded in place on all loadbalancer hosts at once"]
    answer: 0
    explain: "HAProxy is restarted, never reloaded: the handlers stop and start it on the backup hosts first, then on the host that holds the VIP."
    see: "1-the-shared-substrate-what-every-openstack-service-uses"
  - q: "Which statement about the deployment order in <code>site.yml</code> is true?"
    options: ["Neutron is deployed before Nova, so the OVS agent exists when nova-compute starts", "Placement is deployed after Nova", "Nova is deployed before Open vSwitch, OVN and Neutron"]
    answer: 2
    explain: "Nova is deployed before Open vSwitch, OVN and Neutron <span class=\"ev ev-code\">CODE</span>: on a first deploy nova-compute starts before the OVS agent exists. Glance, Cinder and Placement are deployed before Nova."
    see: "6-deployment-order-vs-runtime-dependency"
---

# Component dependencies

This page maps **what depends on what**, and keeps four kinds of dependency apart:

| Kind | Question it answers | Where it lives in the code |
|---|---|---|
| **Installation (deploy-time) dependency** | What must already run for the *role* to succeed? | `kolla_toolbox` calls to MariaDB, Keystone and RabbitMQ in `bootstrap.yml`/`register.yml`, bootstrap containers, `delegate_to` targets |
| **Configuration dependency** | Whose hosts, addresses, flags or passwords end up in *my* config files? | `templates/*.j2`, `group_vars/all.yml` (e.g. `rpc_transport_url`) |
| **Runtime dependency** | What must be reachable for the *service* to work? | The same templates (URLs, connections); upstream OpenStack behaviour |
| **Operational dependency** | Which Kolla action on X changes or restarts Y? | Handlers, global `enable_*` flags, `common`, the loadbalancer play, loop-notify (see [Operations](../operations/index.md)) |

Kolla-Ansible **never declares inter-service dependencies** explicitly. As in 2023.1, no role under `ansible/roles/`
has a `meta` directory, and `common` is its own play (`site.yml:88-103`) [CODE]. Every dependency below is implicit:
play order in `site.yml`, a variable, a template, or a `delegate_to`.

> [!NOTE]
> **Key answers**
>
> - **The database and etcd are reached through the internal VIP and HAProxy; RabbitMQ and memcached hosts are listed
>   one by one in the configs of the services that use them.** Adding or removing a RabbitMQ node therefore changes the
>   config of every messaging service, including `nova-compute` and the neutron agents on every compute; 27 roles loop
>   over the memcached group (33 in 2023.1) [CODE] ([§1](#1-the-shared-substrate-what-every-openstack-service-uses)).
> - **Changed in 2024.1:** RabbitMQ quorum queues are on by default, so the same messaging configs carry
>   `rabbit_quorum_queue = true` ([F17](../reference/findings.md#f17)); `keystone_admin_url` no longer exists; Octavia's
>   jobboard (on by default with the amphora driver) needs Redis, which is off by default [CODE]
>   ([§1](#1-the-shared-substrate-what-every-openstack-service-uses), [§3](#3-control-plane-services)).
> - **A compute host's configuration depends on global state** (enabled services, the membership of the RabbitMQ and
>   memcached groups, the internal VIP, service passwords), not only on the compute host itself. That is why changes
>   that look small trigger fleet-wide restarts [CODE] ([§5](#5-compute-node-dependency-summary)).
> - **What lands on a compute host**, container by container, with the global config source of each
>   ([§5](#5-compute-node-dependency-summary)).
> - **Per-service dependencies:** control-plane services with their use of the DB, RabbitMQ, memcached and Keystone and
>   their deploy-time actions ([§3](#3-control-plane-services)); infrastructure components
>   ([§2](#2-infrastructure-components)); networking containers and their placement
>   ([§4](#4-networking-components-ml2ovs-default-ml2ovn-optional)).
> - **L3 agent:** with `enable_neutron_agent_ha: yes`, the L3 agent wrapper runs
>   `neutron-netns-cleanup --force --agent-type l3` before the agent starts, on every restart or recreate of
>   `neutron_l3_agent` on that host [CODE]; what that command deletes, and the DHCP and router outage per agent
>   restart, are [NOT AVAILABLE] ([§4](#4-networking-components-ml2ovs-default-ml2ovn-optional)).
> - **Deployment order mostly respects runtime dependencies, with caveats:** Nova is deployed before Open vSwitch, OVN
>   and Neutron, and nothing enforces a dependency when you use tags [CODE]
>   ([§6](#6-deployment-order-vs-runtime-dependency)).

A compact card per service (role, play, tags, task flow, templates, handlers, key variables, node types) is in
[Components](index.md). Per-role detail with line references is in the fact sheets
([A](../reference/factsheets/a-infra-lb-ovn.md), [B](../reference/factsheets/b-mariadb-rabbitmq-keystone.md),
[C](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md),
[D](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md),
[E](../reference/factsheets/e-host-bootstrap-ops-playbooks.md)). Nova is covered in depth in [Nova deep
dive](nova-deep-dive.md).

---

## 1. The shared substrate: what every OpenStack service uses

| Shared component | How services reach it | Evidence | Consequence |
|---|---|---|---|
| **MariaDB / Galera** | `database_address: "{{ kolla_internal_fqdn }}"`, i.e. through the **internal VIP and HAProxy** | `ansible/group_vars/all.yml:49, :83` | Every DB connection depends on HAProxy and keepalived as well as on Galera. HAProxy sends DB traffic to **one** active backend; the others are `backup` (`roles/mariadb/defaults/main.yml:29, :64`). With `enable_proxysql: yes` (default `no`, `group_vars/all.yml:839`) the MariaDB load balancer is ProxySQL instead (`mariadb_loadbalancer`, `group_vars/all.yml:481`) ([fact sheet B §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb)) |
| **RabbitMQ** | `rpc_transport_url` / `notify_transport_url` loop over **every host** of `groups['rabbitmq']` (`om_rpc_group`, `om_notify_group`). Clients use their own failover, **not** the VIP | `ansible/group_vars/all.yml:244, :248, :254, :258`; nova-cell builds its own URLs from the same group by default (`roles/nova-cell/defaults/main.yml:191, :200, :206-207`) | Adding or removing a RabbitMQ node changes the config of every messaging service, including `nova-compute` and the neutron agents on **every compute** ([Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller)). **Changed in 2024.1:** `om_enable_rabbitmq_quorum_queues` defaults to `true` (`group_vars/all.yml:268`), rendered as `rabbit_quorum_queue = true` in the `[oslo_messaging_rabbit]` section of these configs (e.g. `roles/nova-cell/templates/nova.conf.j2:207-216`) ([F17](../reference/findings.md#f17)) |
| **Memcached** | Templates loop `{% for host in groups['memcached'] %}` for `keystone_authtoken` / `[cache]` | e.g. `roles/ceilometer/templates/ceilometer.conf.j2:69`; the templates of **27 roles** contain this loop (33 in 2023.1: freezer, murano, sahara, senlin, solum and vitrage are gone). A 28th, telegraf, only tests whether the host itself is in the group (`roles/telegraf/templates/telegraf.conf.j2:54-57`) | Membership change = config change in 27 services ([Memcached](memcached.md)). [NOT AVAILABLE] Whether a memcached restart empties the token caches and the Horizon sessions kept there ([fact sheet A §3.8](../reference/factsheets/a-infra-lb-ovn.md#38-operationally-notable), [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences) item 14) |
| **Keystone** | `www_authenticate_uri`/`auth_url` → internal VIP endpoint (`keystone_internal_url`, `group_vars/all.yml:960`); `service-ks-register` at deploy time | `roles/service-ks-register/tasks/main.yml` (31 roles use it; 37 in 2023.1) | Hard deploy-time dependency: registration runs `run_once` (`roles/service-ks-register/tasks/main.yml:126`) with the `auth` each role passes, e.g. `openstack_nova_auth` (`roles/nova/tasks/register.yml:5`), which is `openstack_auth` (`roles/nova/defaults/main.yml:215`), whose `auth_url` is `keystone_internal_url` (`group_vars/all.yml:990-991`). **No longer holds in 2024.1:** `keystone_admin_url` is gone from `group_vars/all.yml` (2023.1 defined it as the internal URL). Runtime: the services' `[keystone_authtoken]` sections point keystonemiddleware at Keystone, with memcached as token cache (e.g. `roles/nova/templates/nova.conf.j2:112-127`); [NOT AVAILABLE] whether API requests fail while Keystone is down |
| **etcd** (optional, `enable_etcd: "no"`, `group_vars/all.yml:764`) | Through the **internal VIP**: `backend_url = etcd3+…://{{ kolla_internal_fqdn }}:{{ etcd_client_port }}`; the etcd role defines an internal HAProxy frontend | `roles/cinder/templates/cinder.conf.j2:271-281`, `roles/masakari/templates/masakari.conf.j2:97`, `roles/ironic/templates/ironic-inspector.conf.j2:103`; frontend `roles/etcd/defaults/main.yml:11-17`; Redis wins over etcd when both are on (`cinder_coordination_backend`, `group_vars/all.yml:1047`; masakari `:491`, ironic `:1307`) | etcd membership is **not** embedded in service configs: outside the etcd role, only Prometheus's config loops over `groups["etcd"]` (`roles/prometheus/templates/prometheus.yml.j2:214`). Changed in 2024.1: the etcd play has no `serial` (`site.yml:470-481`), and its handlers restart non-leaders in `% 4` waves, then the leader (`roles/etcd/handlers/main.yml:40-65`); on upgrade the order across hosts is [NOT AVAILABLE] (`:28-36`) ([Change control-plane membership](../operations/change-control-plane-membership.md)) |
| **HAProxy + keepalived** | Every internal/admin/public endpoint and the DB address resolve to the VIPs | `roles/*/defaults/main.yml` `haproxy:` dicts → each role's `tasks/loadbalancer.yml` → `roles/loadbalancer-config` → `roles/haproxy-config` (and `roles/proxysql-config` with `enable_proxysql`, `roles/loadbalancer-config/tasks/main.yml:1-8`) | A single point of *path* failure for APIs, DB and etcd. HAProxy is **restarted, never reloaded**: the handlers stop and start it on the backup hosts first, then on the host that holds the VIP (`roles/loadbalancer/handlers/main.yml:36-174, :179-305`) ([fact sheet A §1.8](../reference/factsheets/a-infra-lb-ovn.md#18-operationally-notable-behaviour)). New in 2024.1: a `Restart haproxy-ssh container` handler (`:331-345`) for the `haproxy_ssh` container, enabled only with `enable_letsencrypt` (`roles/loadbalancer/defaults/main.yml:29-36`) ([HAProxy and keepalived](haproxy-keepalived.md)) |
| **fluentd / cron / kolla_toolbox** (`common`) | Deployed on the hosts of the groups `fluentd`, `kolla-toolbox` and `cron` (children of `common`: control, network, compute, storage, monitoring) | `roles/common/defaults/main.yml:5, :14, :26`; `site.yml:88-103`; `inventory/multinode:49-54, :203-213` | `kolla_toolbox` is a **deploy-time** dependency of every role that touches MySQL, Keystone, RabbitMQ or the OVS database (`kolla_toolbox` module needs it running). fluentd is runtime-optional (logging only) ([Common](common.md)) |

```mermaid
flowchart LR
  subgraph Substrate["Shared substrate (runtime)"]
    VIP["keepalived VIP"] --> HAP["HAProxy (haproxy hosts)"]
    HAP --> DB[("MariaDB/Galera<br/>1 active backend")]
    HAP -.optional.-> ETCD[("etcd<br/>(if enable_etcd)")]
    MQ[["RabbitMQ cluster<br/>(direct, all nodes listed)"]]
    MC[("Memcached<br/>(direct, all nodes listed)")]
  end
  KS["Keystone API"] -->|SQL via VIP| HAP
  KS -->|token cache| MC
  SVC["Any OpenStack API / agent"] -->|SQL via VIP| HAP
  SVC -->|RPC + notifications| MQ
  SVC -->|keystonemiddleware cache| MC
  SVC -->|token validation, via VIP| HAP
  HAP -->|"/v3"| KS
```

---

## 2. Infrastructure components

| Component | Role / play | Hosts (example inventory) | Deploy-time needs | Runtime needs | Who depends on it |
|---|---|---|---|---|---|
| **Keepalived** | `loadbalancer` role, `site.yml:105-120` | `loadbalancer` → `network` (`inventory/multinode:84-85`) | `ip_vs` module, sysctl `ip_nonlocal_bind`, now set through the `sysctl` role (`roles/loadbalancer/tasks/config-host.yml:8-25`) | VRRP between loadbalancer hosts (multicast default, `roles/loadbalancer/defaults/main.yml:62`; router id 51, `group_vars/all.yml:224`) | Everything addressed by VIP |
| **HAProxy** | `loadbalancer` role + 39 `loadbalancer.yml` includes (`site.yml:105-327`; 44 in 2023.1) | `loadbalancer` | facts of **all backend hosts** (backend lists use `hostvars[host].ansible_facts.hostname`, `roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:102`) | backends | All APIs, MariaDB (DB address = VIP), etcd |
| **Let's Encrypt** (new in 2024.1) | `letsencrypt` play, right after the loadbalancer play (`site.yml:328-340`) | `letsencrypt` → `loadbalancer` (`inventory/multinode:192-193`) | only if `enable_letsencrypt` (default `no`, `group_vars/all.yml:796`) | – | HAProxy certificates (`haproxy_ssh`) |
| **MariaDB/Galera** | `mariadb` role, `mariadb.yml:3-16` (no `serial`; restarts in separate plays with `serial: "33%"`, `mariadb.yml:18-52`) | `mariadb` → `control` | `kolla_toolbox`; Galera bootstrap logic ([fact sheet B §1](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#1-mariadb-ansiblerolesmariadb)) | HAProxy (clustercheck on port 4569, `group_vars/all.yml:471`) | Every service with a DB |
| **RabbitMQ** | `rabbitmq` role, `rabbitmq.yml:3-28` (no `serial`; restarts with `serial: "33%"`, `rabbitmq.yml:30-49`) | `rabbitmq` → `control` | erlang cookie, `/etc/hosts` (from `bootstrap-servers`, ansible-collection-kolla `roles/baremetal/tasks/main.yml:3`, role `etc_hosts`) | – | Every service with RPC/notifications ([RabbitMQ](rabbitmq.md)) |
| **Memcached** | `memcached` role, `site.yml:402-414` | `memcached` → `control` | – | – | Keystone, all keystonemiddleware users, Horizon sessions |
| **etcd** | `etcd` role, `site.yml:470-481` (no `serial` in 2024.1) | `etcd` → `control` (`inventory/multinode:62-63`) | only if `enable_etcd` | – | Cinder, Masakari, ironic-inspector coordination when chosen ([§1](#1-the-shared-substrate-what-every-openstack-service-uses)) |
| **Redis** | `redis` role, `site.yml:384-398` | `redis` → `control` (`inventory/multinode:183-184`) | only if `enable_redis` (default `no`, `group_vars/all.yml:840`) | – | Coordination backends when enabled; **Octavia jobboard** ([§3](#3-control-plane-services)) |
| **Fluentd** | `common` play, `site.yml:88-103` | `fluentd` → `common` (all node types) | the fluentd image, pulled and inspected even by a config-only run (`roles/common/tasks/config.yml:42-91`, [Common](common.md)) | (optional) Elasticsearch or OpenSearch outputs (`roles/common/tasks/config.yml:140-203`) | Logging only. HAProxy syslogs to fluentd UDP (`roles/loadbalancer/templates/haproxy/haproxy_main.cfg.j2:7`, `group_vars/all.yml:630`) |
| **Open vSwitch** | `openvswitch` role, `site.yml:611-624` | `openvswitch` → `network`, `compute`, `manila-share` (`inventory/multinode:105-108`) | kernel module `openvswitch` (`roles/openvswitch/tasks/config-host.yml:2-7`); `neutron_bridge_name`/`neutron_external_interface` on network nodes (and computes if `computes_need_external_bridge`) | – | neutron-openvswitch-agent, OVN controller, DHCP/L3 agents |
| **OVN** (if `neutron_plugin_agent: ovn`) | `ovn-controller` role, `site.yml:641`, and `ovn-db` role, `site.yml:655` | `ovn-database` → `control`; `ovn-controller` → `compute`, `network` (`inventory/multinode:593-604`) | OVS running (ovn-controller's setup creates `br-int` and writes OVS `external_ids` through the `openvswitch_bridge` and `openvswitch_db` modules in `kolla_toolbox`, `roles/ovn-controller/tasks/setup-ovs.yml:2-40`) | NB/SB DB cluster (Raft) | neutron-server (ML2/OVN), neutron-ovn-metadata-agent |
| **Chrony** | **none in 2024.1**: no `roles/chrony`, no chrony play in `site.yml`, no `chrony` group in `inventory/multinode` ([Chrony](chrony.md)) | – (host NTP daemon, outside Kolla-Ansible) | `kolla-ansible prechecks` checks that a host NTP daemon is active and the clock synchronised (`roles/prechecks/tasks/timesync_checks.yml:1-47`) | the host's NTP daemon | [NOT AVAILABLE] in the code: which services need synchronised clocks |
| **iscsid / tgtd** | `iscsi` role, `site.yml:439-452` | `iscsid` → `compute`, `storage`, `ironic`; `tgtd` → `storage` (`inventory/multinode:305-311`) | only if `enable_iscsid` (cinder with the iSCSI backend, `group_vars/all.yml:794`) | – | nova-compute (volume attach), cinder-volume (LVM) ([iSCSI](iscsi.md)) |

### 2.1 Infrastructure dependency graph (runtime)

```mermaid
flowchart TB
  KA["keepalived"] -->|VIP| HAP["HAProxy"]
  HAP -->|"tcp 3306 (1 active)"| DB[("MariaDB/Galera")]
  HAP -->|HTTP| KS["Keystone"]
  HAP -.->|"2379 (if enabled)"| ETCD[("etcd")]
  KS --> MC[("Memcached")]
  KS -->|"SQL via VIP"| HAP
  OVS["openvswitch_db + vswitchd"] --> OVSAG["neutron-openvswitch-agent"]
  OVS --> OVNC["ovn-controller"]
  OVNC --> SB[("OVN SB DB")]
  NORTHD["ovn-northd"] --> NB[("OVN NB DB")] & SB
  FL["fluentd (all hosts)"] -.optional.-> ES[("Elasticsearch / OpenSearch")]
  TB["kolla_toolbox (all hosts)"] -.deploy-time only.-> DB & KS & MQ[["RabbitMQ"]]
```

---

## 3. Control-plane services

Legend: **DB** = MariaDB through the VIP, **MQ** = RabbitMQ (all nodes listed), **MC** = memcached, **KS** = Keystone. A
✔ means the role's config templates (`roles/<role>/templates/*.j2`) reference it [CODE]. Every role below except Swift
runs its deploy steps on `reconfigure` too: its `reconfigure.yml` imports `deploy.yml` (e.g.
`roles/keystone/tasks/reconfigure.yml:2`) [CODE]. What each bootstrap container runs inside the image is listed in
[Kolla images §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run).

| Service | DB | MQ | MC | KS | Other services referenced in config | Deploy-time actions | Notes (fact sheet) |
|---|---|---|---|---|---|---|---|
| **Keystone** | ✔ | ✔ (`roles/keystone/templates/keystone.conf.j2:4, :54`) | ✔ | – | – | bootstrap container (db sync) **every deploy/reconfigure**, no condition (`roles/keystone/tasks/bootstrap_service.yml:33-50`); fernet keys pushed from the first host where `keystone_fernet` runs (`roles/keystone/tasks/distribute_fernet.yml:12-18`); admin bootstrap through `kolla_keystone_bootstrap` (`roles/keystone/tasks/register.yml:2-11`) | [B §3.6–3.10](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#36-fernet-key-lifecycle-fact-unless-marked), [Keystone](keystone.md) |
| **Glance** | ✔ | ✔ | ✔ | ✔ | Cinder (store), Ceph, Swift, S3 (new store, `glance_backend_s3`, default `no`, `group_vars/all.yml:1004`), Barbican | db sync + `db_load_metadefs` on every deploy/reconfigure (kolla `docker/glance/glance-api/extend_start.sh:5-9`); toggles **global** MariaDB `log_bin_trust_function_creators` (`roles/glance/tasks/bootstrap_service.yml:2-12, :39-49`) | [C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance). With the file backend only `groups['glance-api'][0]` runs glance (`group_vars/all.yml:1011`) |
| **Placement** | ✔ | – | ✔ | ✔ | (Nova credentials in migration helper) | db sync **and online data migrations** on every deploy/reconfigure (one `KOLLA_BOOTSTRAP` container, kolla `docker/placement/placement-api/extend_start.sh:5-9`) | [C §2](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#2-placement). The placement templates have no `transport_url` (the 2023.1 table showed "✔ (unused)") |
| **Nova** | ✔ | ✔ | ✔ (API side only; nova-cell's `nova.conf` has no memcached list) | ✔ | Glance, Neutron, Placement, Cinder, Barbican, Ceph | API/cell0/cell DB sync on every deploy/reconfigure; cell create/update; host discovery | [Nova deep dive](nova-deep-dive.md) |
| **Neutron** | ✔ (server) | ✔ | ✔ | ✔ | Nova (notifications to Nova), Placement, OVN | DB, user and grants, and the `bootstrap_neutron` db sync container, on every deploy/reconfigure (`roles/neutron/tasks/bootstrap.yml:38`, `bootstrap_service.yml:2-21`, no condition; `neutron_enable_rolling_upgrade` only selects the upgrade path, `roles/neutron/tasks/upgrade.yml:4-8`) | [§4](#4-networking-components-ml2ovs-default-ml2ovn-optional) below |
| **Cinder** | ✔ | ✔ | ✔ | ✔ | Glance, Nova (uses **nova** credentials), Barbican, Swift (backup), Ceph; etcd through the internal VIP when `cinder_coordination_backend` is `etcd`, or Redis (all hosts listed in `redis_connection_string`, `group_vars/all.yml:893`) when it is `redis` (`roles/cinder/templates/cinder.conf.j2:271-281`, `group_vars/all.yml:1047`) | db sync on every deploy/reconfigure (`roles/cinder/tasks/deploy.yml:11`) | [C §3](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#3-cinder) |
| **Horizon** | only if `horizon_backend_database` (default `false`, `group_vars/all.yml:1141`) | – | ✔ (sessions, `roles/horizon/templates/_9998-kolla-settings.py.j2:19-23`) | ✔ | every enabled API (internal endpoint type, `_9998-kolla-settings.py.j2:131`) | no Keystone registration | [C §4](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#4-horizon). Changed in 2024.1: the settings template is `_9998-kolla-settings.py.j2` (`local_settings.j2` is gone) |
| **Heat** | ✔ | ✔ | ✔ | ✔ | every API used by templates (internal); instances need the **external** CFN endpoint | db sync on every deploy/reconfigure; heat domain admin setup only when `heat_user_domain` does not exist yet (kolla `docker/heat/heat-api/extend_start.sh:8-14`): a changed `heat_domain_admin_password` reaches `heat.conf` (`roles/heat/templates/heat.conf.j2:12`) but is never applied in Keystone | [C §5](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#5-heat) |
| **Barbican** | ✔ | ✔ | ✔ | ✔ | – | db sync on every deploy/reconfigure (`roles/barbican/tasks/deploy.yml:11`); `barbican_crypto_key` from `passwords.yml` | [D §1](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#1-barbican) |
| **Octavia** | ✔ (two databases: main and persistence, `roles/octavia/tasks/bootstrap.yml:2-72`) | ✔ | ✔ | ✔ | Nova, Neutron, Glance (amphora image, flavor, network, secgroup); **Redis** for the jobboard (every host of `groups['redis']`, `roles/octavia/templates/octavia.conf.j2:177-187`) | db sync; with `octavia_auto_configure` (true when the `amphora` provider is listed, the default; `group_vars/all.yml:1323`, `roles/octavia/defaults/main.yml:386`) `prepare.yml` creates the amphora flavor, keypair, security groups and management network, subnet and router (`roles/octavia/tasks/deploy.yml:4-5`, `prepare.yml:2-161`); the amphora image stays manual. **New in 2024.1:** `enable_octavia_jobboard` is on whenever Octavia uses the amphora provider (`group_vars/all.yml:832`) and the precheck fails unless `enable_redis` is set (`roles/octavia/tasks/precheck.yml:67-73`; `enable_redis` defaults to `no`, `group_vars/all.yml:840`) | [D §2](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#2-octavia) |
| **Swift** | – | ✔ (notifications, `roles/swift/templates/proxy-server.conf.j2:62`) | ✔ | ✔ | – | rings are operator-built; old-style deploy flow: register, config, start, check, with no check-containers step (`roles/swift/tasks/deploy.yml:2-10`); its `reconfigure.yml` has its own flow | [D §3](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#3-swift) |
| **Manila** | ✔ | ✔ | ✔ | ✔ | Glance, Neutron, Nova, Cinder, Ceph (CephFS) | db sync; manila-share hosts also get the Open vSwitch agent with the generic backend (`roles/neutron/defaults/main.yml:36`) | [D §4](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#4-manila) |

### 3.1 Control-plane runtime graph

```mermaid
flowchart LR
  USER(("API clients<br/>Horizon")) --> HAP["HAProxy VIP"]
  HAP --> KS["Keystone"] & GL["Glance API"] & PL["Placement API"] & NA["Nova API"] & NS["Neutron server"] & CA["Cinder API"] & HA["Heat API/CFN"] & BA["Barbican API"] & OA["Octavia API"] & SW["Swift proxy"] & MA["Manila API"]
  NA -->|RPC| NSC["nova-scheduler"] --> PL
  NA --> NCOND["nova-conductor"]
  NS -->|"port events (os-server-external-events)"| NA
  NA -->|ports| NS
  NA -->|images| GL
  NA -->|volumes| CA
  CA -->|images| GL
  CA -.->|"nova creds: volume events"| NA
  GL -.->|store| CA
  GL -.->|store| SW
  HA -->|"orchestrates (internal endpoints)"| NA & NS & CA & GL
  OA -->|amphorae| NA & NS & GL
  OA -.->|"jobboard"| RD[("Redis")]
  MA -->|share servers| NA & NS & CA
  NA & NS & CA & GL & PL & HA & BA & OA & MA -->|tokens| KS
```

The dotted edges are configuration couplings that are easy to overlook:

- **Cinder → Nova** with Nova's own credentials (`roles/cinder/templates/cinder.conf.j2:109-119`).
- **Glance → Cinder or Swift** as image stores. Enabling Swift *changes Glance's default backend*:
  `glance_backend_swift` follows `enable_swift` (`group_vars/all.yml:1006`), and `glance_default_backend` picks `swift`
  unless VMware or Ceph is set (`roles/glance/defaults/main.yml:247`) ([fact sheet C
  §1.8](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#18-operational-notes)).
- **Nova and Neutron → Placement** with the placement user (`roles/nova-cell/templates/nova.conf.j2:234-244`).
- **Octavia → Redis**, new in 2024.1: the jobboard lists every Redis host, and it is on by default with the amphora
  provider (`roles/octavia/templates/octavia.conf.j2:177-187`, `group_vars/all.yml:832`).

---

## 4. Networking components (ML2/OVS default, ML2/OVN optional)

| Container | Placement rule (`host_in_groups`) | Needs | Data-plane role |
|---|---|---|---|
| `openvswitch_db`, `openvswitch_vswitchd` | compute, manila-share (generic backend), dhcp/l3/metadata agent hosts (`roles/openvswitch/defaults/main.yml:2-34`) | kernel module, `/run/openvswitch` | **Forwards all VM traffic** |
| `neutron_openvswitch_agent` | compute, manila-share (generic), dhcp/l3/metadata hosts (`roles/neutron/defaults/main.yml:26-46`; with `enable_nova_fake` only the dhcp/l3/metadata hosts) | OVS, RabbitMQ, (neutron-server via RPC) | Programs OVS flows; [NOT AVAILABLE] whether and how it resyncs them after a restart ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)) |
| `neutron_l3_agent` | `neutron-l3-agent`; **plus every compute** when `enable_neutron_dvr` (`roles/neutron/defaults/main.yml:85-89`) | OVS, `/run/netns` | Routers (namespaces, keepalived for HA routers) |
| `neutron_dhcp_agent` | `neutron-dhcp-agent` | OVS | dnsmasq per network |
| `neutron_metadata_agent` | `neutron-metadata-agent`; plus computes with DVR and ML2/OVS (`roles/neutron/defaults/main.yml:122-126`) | nova-api metadata via VIP (`nova_metadata`) | metadata proxy |
| `neutron_server` | `neutron-server` | DB, MQ, KS, Nova, Placement | control plane only |
| `ovn_controller` (OVN) | `ovn-controller` (compute + network; role `ovn-controller`) | OVS, SB DB | Programs OVS from SB DB |
| `neutron_ovn_metadata_agent` (OVN) | `neutron-ovn-metadata-agent` → compute, network (`inventory/multinode:264-266`; `roles/neutron/defaults/main.yml:135`) | OVS, SB DB | metadata per chassis |

```mermaid
flowchart TB
  subgraph Compute["Compute host (ML2/OVS)"]
    NC["nova_compute"] -->|"vif plug (os-vif → ovsdb)"| OVSDB[("openvswitch_db")]
    NL["nova_libvirt / qemu"] -->|tap devices| VS["openvswitch_vswitchd"]
    OA["neutron_openvswitch_agent"] -->|flows| VS
    OA --> OVSDB
    VS --- OVSDB
  end
  subgraph Network["Network host"]
    L3["neutron_l3_agent<br/>(router namespaces, keepalived)"] --> VS2["openvswitch_vswitchd"]
    DHCP["neutron_dhcp_agent (dnsmasq)"] --> VS2
    MD["neutron_metadata_agent"]
    OA2["neutron_openvswitch_agent"] --> VS2
  end
  subgraph Control["Controller"]
    NS["neutron_server"]
  end
  OA & OA2 & L3 & DHCP & MD -->|RPC| MQ[["RabbitMQ"]]
  NS --> MQ
  NS -->|"port bound/unbound events"| NAPI["nova-api"]
  NC -->|"port create/update"| NS
  MD -->|"proxy to nova metadata (VIP)"| NAPI
```

Runtime facts [CODE]:

- **The L3 agent wrapper runs a namespace cleanup on start.** With `enable_neutron_agent_ha: yes` (default `no`,
  `group_vars/all.yml:816`), its start wrapper runs `neutron-netns-cleanup --force --agent-type l3` *before* starting
  the agent (`roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:5-14`; new in 2024.1, it also reads
  `fwaas_driver.ini` when `enable_neutron_fwaas` is set, `:10-12`), on every restart or recreate of `neutron_l3_agent`
  on such a host (the wrapper's comment: "Remove all l3 related netns"). [NOT AVAILABLE] What the command deletes: it
  is neutron code, which is not in these sources ([F12](../reference/findings.md#f12)); whether and when
  `neutron-l3-agent` rebuilds the namespaces ([Risk register R6](../risk/risk-register.md#r6)).
- **Agent containers do not share the host PID namespace.** They have no `pid_mode` (`roles/neutron/defaults/main.yml`).
  Processes they spawn (dnsmasq, keepalived, haproxy for metadata) live in the container's PID namespace.
  [NOT AVAILABLE] Whether they die with the container and are respawned by the agent on start. For the L3 agent, its
  wrapper starts `neutron-l3-agent` without `exec`, and dumb-init runs with `--single-child` (kolla
  `docker/base/Dockerfile.j2:370`; `roles/neutron/templates/neutron-l3-agent-wrapper.sh.j2:16-20`) [CODE].
  [NOT AVAILABLE] Whether the SIGTERM of the stop then reaches only bash and not the agent, and so whether the
  agent gets a graceful shutdown: that depends on how dumb-init forwards signals, which these sources do not show
  ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1),
  [§5.3](../concepts/kolla-images.md#53-neutron-l3-agent-the-wrapper)). [NOT AVAILABLE] The DHCP and router outage per
  agent restart.
- **The OVS bridge layout is set in a post-config step, now through `kolla_toolbox` modules.** On every
  deploy/reconfigure (`roles/openvswitch/tasks/deploy.yml:11`; `reconfigure.yml` imports `deploy.yml`), on network
  hosts (and computes with `computes_need_external_bridge`), the bridges are ensured by the `openvswitch_bridge` module
  (`fail_mode: standalone`) and their ports by `openvswitch_port` (`roles/openvswitch/tasks/post-config.yml:25-53`).
  **Changed in 2024.1:** the image script `kolla_ensure_openvswitch_configured` is no longer called. The same file first
  sets `external_ids:system-id`, the new `external_ids:hostname` (the host's FQDN,
  `roles/openvswitch/defaults/main.yml:106`)
  and `other_config:hw-offload`; a change there notifies `Restart openvswitch-vswitchd container`
  (`post-config.yml:3-23`) [CODE] ([Open vSwitch](openvswitch.md)).

---

## 5. Compute-node dependency summary

Everything that lands on a compute host in a default 2024.1 deployment (`enable_*` defaults in
`ansible/group_vars/all.yml:718-867`, placement from each role's `<role>_services`):

| Container | Role | Config source that is *global* (changes fleet-wide) |
|---|---|---|
| `fluentd`, `cron`, `kolla_toolbox` | common | `td-agent.conf` and `logrotate.conf` built from **all** `enable_*` flags (`roles/common/tasks/config.yml:140-270`) |
| `chrony` | none in 2024.1 | no chrony container or `chrony.conf`: there is no `roles/chrony` and no chrony play ([Chrony](chrony.md)); time sync is the host's NTP daemon |
| `iscsid` | iscsi (if cinder with the iSCSI backend, `group_vars/all.yml:794`) | – |
| `nova_libvirt`, `nova_ssh`, `nova_compute` | nova-cell | `nova.conf`: `transport_url` (all RabbitMQ hosts, `roles/nova-cell/templates/nova.conf.j2:37, :184`), quorum-queue flags (`:207-216`), `enable_ceilometer/watcher/cinder/osprofiler/barbican…` sections, Glance, Neutron and Placement endpoints, service passwords |
| `openvswitch_db`, `openvswitch_vswitchd` | openvswitch | – (bridge mappings only if `computes_need_external_bridge`) |
| `neutron_openvswitch_agent` | neutron | `neutron.conf` (all RabbitMQ hosts, memcached list, `roles/neutron/templates/neutron.conf.j2:123`) **and** `openvswitch_agent.ini` (merged from the role template, the operator's `openvswitch_agent.ini` and the per-host `<inventory_hostname>/openvswitch_agent.ini`; no `ml2_conf.ini` override, `roles/neutron/tasks/config.yml:198-213`) |

Optional compute-side containers come from ceilometer, collectd, telegraf, prometheus exporters, masakari, zun, kuryr
and cyborg (skydive and monasca have no role in 2024.1) ([fact sheet D
§5](../reference/factsheets/d-barbican-octavia-swift-manila-compute-roles.md#50-summary-table-compute-side)). Several of
them embed host lists from other groups in their config: memcached (ceilometer, masakari, zun, cyborg), RabbitMQ
through the transport URLs, and for telegraf the `influxdb` group among others (`grep` of `groups[...]` in
`roles/<role>/templates`) [CODE]. No compute-side template lists the etcd hosts (see
[§1](#1-the-shared-substrate-what-every-openstack-service-uses)). The full list of templates that loop over groups is
in [Generated inventory §4](../reference/generated-inventory.md#4-templates-that-reference-inventory-groups).

**Rule of thumb [CODE]:** a compute host's configuration depends on *global* state (enabled services, the membership of
the RabbitMQ and memcached groups, the internal VIP, service passwords, and in 2024.1 the RabbitMQ queue-type defaults),
not only on the compute host itself. That is why changes that look small trigger fleet-wide restarts ([Compute
scaling](../concepts/compute-scaling-and-performance.md), [F6](../reference/findings.md#f6),
[Operations](../operations/index.md)). Changed from 2023.1: the etcd group no longer belongs in this list, because no
service template outside Prometheus embeds it.

---

## 6. Deployment order vs runtime dependency

Deployment order is the play order in `site.yml` ([Execution flow](../concepts/deployment-execution-flow.md)). It mostly
respects runtime dependencies, with these caveats [CODE]:

| Observation | Evidence | Effect |
|---|---|---|
| HAProxy is configured for **all** services before any of them exists | `site.yml:105-327` (the loadbalancer play, right after `common`), then Let's Encrypt (`:328-340`) | The first deploy puts frontends in place for backends not yet started. Each backend server is health-checked (`check inter 2000 rise 2 fall 5`, `roles/haproxy-config/defaults/main.yml:14`); how HAProxy treats a backend that is not up yet is [NOT AVAILABLE] |
| Redis, MariaDB, memcached, RabbitMQ and etcd come before Keystone | `site.yml:384` (redis), `:400` (`mariadb.yml`), `:402` (memcached), `:468` (`rabbitmq.yml`), `:470` (etcd), `:483` (keystone) | The substrate exists when the first service registers and syncs its DB |
| **Placement is deployed before Nova; Glance and Cinder too** | `site.yml:544-608` (glance `:544`, cinder `:576`, placement `:593`; `nova.yml` at `:609`) | Nova bootstrap can use Placement and Glance at once |
| **Nova is deployed *before* Open vSwitch, OVN and Neutron** | `site.yml:609` (`nova.yml`) vs `:611-694` | On a first deploy nova-compute starts before the OVS agent exists, and Kolla waits for its registration in the nova-cell play, before the OVS and Neutron plays run (`roles/nova-cell/tasks/deploy.yml:19-37`, `wait_discover_computes.yml:7-20`) ([F13](../reference/findings.md#f13)). [NOT AVAILABLE] Whether instances can be scheduled there before those plays finish ([Execution flow §2.4](../concepts/deployment-execution-flow.md#24-compute-node-deployment-what-one-compute-host-experiences)) |
| Heat, Horizon and Octavia come after Nova and Neutron | `site.yml:724-997` (heat `:724`, horizon `:740`, octavia `:981`) | – |
| Nothing enforces a dependency when you **use tags** | `--tags` filters plays | `-t nova` on a fresh cloud reaches Keystone registration (`service-ks-register`, against `keystone_internal_url`) with no Keystone deployed. On an existing cloud it assumes MariaDB, RabbitMQ and Keystone are healthy. With `-t octavia` and the 2024.1 defaults, the Octavia config lists the Redis hosts whether or not Redis was deployed |
| Bootstrap and registration tasks target `groups[...][0]` | e.g. `roles/nova-cell/tasks/bootstrap.yml:15, :34`; `roles/keystone/tasks/bootstrap.yml:14, :34` | The first host of a group is a hidden dependency: it must be reachable and have `kolla_toolbox` running |

## Related

- [Nova deep dive](nova-deep-dive.md) (Nova in depth)
- [Operations](../operations/index.md) (what these dependencies do to a Day-2 run)
- [Execution flow](../concepts/deployment-execution-flow.md) (deployment order)
- [Components](index.md) (service index)
