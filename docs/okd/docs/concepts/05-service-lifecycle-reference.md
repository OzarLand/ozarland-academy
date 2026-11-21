---
title: "Service lifecycle reference"
description: "All services follow the same pattern. Learn it once on Keystone and the others differ only in details."
---

# Service lifecycle reference

> Status: aligned with the lab deployed on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); explanatory page, commands spot-checked against the validated guides

## In short

- A reference page, not a page to read in one go: one card per service of
  the lab, with its operator, its custom resources (CRs), its Kubernetes
  workload, its storage and what is particular about its lifecycle.
- All services follow the same pattern: inspect the CR and its conditions,
  configure through the `OpenStackControlPlane` CR, restart by deleting the
  pod.
- Every service runs with 1 replica: every restart is a short outage of that
  service.
- Galera, RabbitMQ, the OVN databases and Glance hold persistent data; the
  [quick reference](#quick-reference) at the end summarises all services.

## How to read the cards

All services follow the same pattern. Learn it once on Keystone and the others
differ only in details.

| Operation | General method | Validated procedure |
|---|---|---|
| Inspect | `oc get <cr-kind> -n openstack`, then its conditions, then pods and logs | [Inspect service status](../operations/01-inspect-service-status.md), [Logs](../operations/02-logs.md) |
| Configure | Edit `spec.<service>.template` of the `OpenStackControlPlane` CR; the operator rolls the pods of that service | [Change service configuration](../operations/04-change-service-configuration.md) |
| Restart | Delete the pod; its Deployment or StatefulSet recreates it | [Restart a service](../operations/03-restart-a-service.md) |
| Scale | Change `replicas` in the `OpenStackControlPlane` CR | [Scale a service](../operations/06-scale-a-service.md) |
| Disable / enable | `spec.<service>.enabled` in the `OpenStackControlPlane` CR | [Enable a service](../operations/05-enable-a-service.md) |
| Update images | `spec.targetVersion` of the `OpenStackVersion` CR (all services, in a fixed order) | [Minor update](../lifecycle/01-openstack-version-and-minor-update.md) |

Shared facts:

- **Restart means deleting the pod, not `oc rollout restart`.** The pod
  template belongs to the operator, which removes the restart annotation
  within a second; `oc scale` is reverted the same way. The observed effects
  are listed in
  [Why manual edits of managed objects do not stick](03-operators-crds-and-reconciliation.md#why-manual-edits-of-managed-objects-do-not-stick).
- Every service runs with 1 replica, so **every restart is a short outage of
  that service** (20 to 60 seconds on the lab, mostly the readiness probe,
  the check a pod must pass before it receives traffic). Running instances
  and their networking are not affected by API restarts.
- Pod logs: `oc logs -n openstack <pod> [-c <container>]`. Operator logs:
  `oc logs -n openstack-operators deployment/<operator>-operator-controller-manager`.
- Database schema migrations (`db-sync`) run as Jobs, created by the operator
  when the image or the configuration changes and deleted once they succeed.

Dependency order (what must be ready before what) is the familiar one:

```text
cert-manager CA ─▶ Galera, RabbitMQ, Memcached ─▶ Keystone ─▶ Placement, Glance, Neutron(+OVN) ─▶ Nova
```

---

## Galera (MariaDB)

| | |
|---|---|
| Operator | `mariadb-operator` |
| CRs | `Galera` (the cluster); `MariaDBDatabase`, `MariaDBAccount` (schemas and users, created by the other operators); `GaleraBackup`, `GaleraRestore` |
| Instances in the lab | `openstack` (API databases) and `openstack-cell1` (Nova cell1) |
| Workload | StatefulSets `openstack-galera` and `openstack-cell1-galera`, one pod each |
| Storage | PVCs `mysql-db-openstack-galera-0` and `mysql-db-openstack-cell1-galera-0` |
| Control plane section | `spec.galera.templates.<instance>` |

- **Bootstrap.** The operator, not you, decides which node bootstraps the
  cluster; this replaces `kolla-ansible mariadb_recovery`. With the single
  replica of the lab, the pod bootstrapped by itself in about 20 seconds after
  a pod deletion, after `kill -9` of `mysqld`, and after a node reboot.
- **Inspect.** `oc get galera -n openstack`;
  `oc logs -n openstack openstack-galera-0 -c galera`;
  `oc exec -n openstack openstack-galera-0 -c galera -- mysql -uroot -e 'SHOW DATABASES;'`.
- **Restart.** Delete the pod. Every API fails for the duration.
- **Backup.** A `GaleraBackup` CR schedules logical dumps to a dedicated PVC;
  executed on the lab, see
  [Backup and restore](../lifecycle/05-backup-and-restore.md).
- **Never delete its PVC.** See the
  [Galera and RabbitMQ runbook](../troubleshooting/galera-and-rabbitmq.md).

## RabbitMQ

| | |
|---|---|
| Operator | `infra-operator` |
| CRs | `RabbitMq` (the cluster); `TransportURL` (a consumer's connection, created by service operators) |
| Instances in the lab | `rabbitmq` and `rabbitmq-cell1` |
| Workload | StatefulSets `rabbitmq-server` and `rabbitmq-cell1-server`, one pod each |
| Storage | PVCs `persistence-rabbitmq-server-0` and `persistence-rabbitmq-cell1-server-0` |
| Control plane section | `spec.rabbitmq.templates.<instance>` |

- **Inspect.** `oc get rabbitmq,transporturl -n openstack`;
  `oc exec -n openstack rabbitmq-server-0 -- rabbitmqctl cluster_status`;
  `oc exec -n openstack rabbitmq-server-0 -- rabbitmqctl list_queues name messages consumers`.
- **Restart.** Delete the pod (`rabbitmq-server-0` was ready again after about
  60 seconds on the lab). Services reconnect by themselves; the control plane
  resource goes `False` for a while and returns to `True` unaided.
- **No scale to zero.** The admission webhook refuses `replicas: 0`.
- **Footprint.** Each instance requests 1 CPU and 2Gi of memory; they are the
  only OpenStack pods of the lab with resource requests.
- **Data plane dependency.** `nova-compute` on compute nodes connects to
  `rabbitmq-cell1`, which is why both instances have a MetalLB address on the
  internalapi network (172.17.0.85 and 172.17.0.86).

## Memcached

| | |
|---|---|
| Operator | `infra-operator` |
| CR | `Memcached` |
| Workload | StatefulSet `memcached`, pod `memcached-0` |
| Storage | None |
| Control plane section | `spec.memcached.templates.memcached` |

Stateless cache. Deleting the pod only flushes caches.

## DNS (dnsmasq)

| | |
|---|---|
| Operator | `infra-operator` |
| CRs | `DNSMasq` (the server), `DNSData` (records, created by other operators), `NetConfig` / `IPSet` (address management for data plane nodes) |
| Workload | Deployment `dnsmasq-dns`, label `service=dnsmasq` |
| Storage | None |
| Control plane section | `spec.dns.template` |

This is **not** Designate. It is a small internal DNS server, published on the
ctlplane network (192.168.122.80), that compute nodes use as their resolver:
it answers for control plane service names and node names and forwards the
rest to the bastion. See
[DNS and routing](../troubleshooting/dns-and-routing.md).

## Keystone

| | |
|---|---|
| Operator | `keystone-operator` |
| CRs | `KeystoneAPI` (the service); `KeystoneService`, `KeystoneEndpoint` (catalog entries, created by every other service operator) |
| Workload | Deployment `keystone`, label `service=keystone`, container `keystone-api` |
| Jobs | `keystone-db-sync`, `keystone-bootstrap` (deleted after success); CronJob `keystone-cron` |
| Storage | None |
| Control plane section | `spec.keystone.template` |

- **Inspect.** `oc get keystoneapi,keystoneservice,keystoneendpoint -n openstack`;
  `oc logs -n openstack deployment/keystone`.
- **Catalog.** Endpoints are declared by `KeystoneEndpoint` CRs. The operator
  does not watch the Keystone database: an endpoint changed with
  `openstack endpoint set` stays wrong until the next reconcile of that CR
  (see
  [Kubernetes resource versus OpenStack resource](03-operators-crds-and-reconciliation.md#kubernetes-resource-versus-openstack-resource)).
- **Service passwords** are not pushed to Keystone when `osp-secret` changes;
  see [Passwords and secrets](../operations/07-passwords-and-secrets.md).
- **Restart.** Delete the pod (ready again after about 35 seconds on the lab).

## Placement

| | |
|---|---|
| Operator | `nova-operator` (the `placement.openstack.org` group has no Deployment of its own) |
| CR | `PlacementAPI` |
| Workload | Deployment `placement`, label `service=placement` |
| Storage | None |
| Control plane section | `spec.placement.template` |

Stateless API in front of the `placement` database. Inspect with
`oc get placementapi -n openstack` and, on the OpenStack side,
`openstack resource provider list`.

## Glance

| | |
|---|---|
| Operator | `glance-operator` |
| CRs | `Glance` (top level), `GlanceAPI` (one per entry under `glanceAPIs`) |
| Workload | StatefulSet `glance-default-single`, pod `glance-default-single-0`, label `service=glance` |
| Storage | PVC `glance-glance-default-single-0`, the image store |
| Control plane section | `spec.glance.template` |

- **Backend** is configured through `customServiceConfig`
  (`enabled_backends`, `[glance_store]`...). The upstream sample uses Swift;
  the lab uses the file store on the PVC because Swift is disabled.
- **API layout.** With a file store the admission webhook requires the single
  API layout (`type: single` in the lab manifest), hence the workload name.
- With one replica, the PVC is the only copy of the images.
- Enabling or disabling Horizon rolls the Glance pod once (observed on the
  lab).

## OVN

| | |
|---|---|
| Operator | `ovn-operator` |
| CRs | `OVNDBCluster` (two: northbound and southbound), `OVNNorthd` |
| Workloads | StatefulSets `ovsdbserver-nb`, `ovsdbserver-sb` and `ovn-northd` |
| Storage | PVCs `ovndbcluster-nb-etc-ovn-ovsdbserver-nb-0` and `ovndbcluster-sb-etc-ovn-ovsdbserver-sb-0` |
| Control plane section | `spec.ovn.template` (`ovnDBCluster`, `ovnNorthd`, `ovnController`) |

- **Do not confuse it with OVN-Kubernetes**, the network plugin of OKD itself,
  which lives in `openshift-ovn-kubernetes`. They are two independent OVN
  deployments; the one described here serves Neutron only.
- **No `ovn-controller` on the OKD node.** The lab control plane has no
  `OVNController` resource and no DaemonSet: `ovn-controller` runs only on the
  compute node, as a podman container under systemd (`edpm_ovn_controller`).
- **Inspect.** `oc get ovndbcluster,ovnnorthd -n openstack`;
  `oc get pods -n openstack -l service=ovsdbserver-sb`.
- **Data plane dependency.** `ovn-controller` on every compute node connects
  to the **southbound** database on the internalapi address of its pod
  (a network attachment, not a MetalLB address).

## Neutron

| | |
|---|---|
| Operator | `neutron-operator` |
| CR | `NeutronAPI` |
| Workload | Deployment `neutron`, label `service=neutron` |
| Storage | None |
| Control plane section | `spec.neutron.template` |

Only `neutron-server` (ML2/OVN) runs on the control plane. There are no L3,
DHCP or Open vSwitch agents: OVN provides those functions. The only Neutron
agent in the lab is the OVN metadata agent on the compute node, deployed by
the data plane. `openstack network agent list` shows an
`OVN Controller Gateway agent` and an `OVN Metadata agent` per compute node.

## Nova

| | |
|---|---|
| Operator | `nova-operator` |
| CRs | `Nova` (top level), `NovaAPI`, `NovaScheduler`, `NovaMetadata`, and per cell `NovaCell`, `NovaConductor`, `NovaNoVNCProxy` |
| Workloads | StatefulSets `nova-api`, `nova-scheduler`, `nova-metadata`, `nova-cell0-conductor`, `nova-cell1-conductor`, `nova-cell1-novncproxy` |
| Storage | None |
| Control plane section | `spec.nova.template` (`apiServiceTemplate`, `schedulerServiceTemplate`, `metadataServiceTemplate`, `cellTemplates.<cell>`) |

- **Cells are explicit.** `cell0` and `cell1` are entries under
  `cellTemplates`, each naming its database instance (`cellDatabaseInstance`)
  and its message bus (`messagingBus.cluster`).
- **Per-component configuration.** `customServiceConfig` exists at the top
  level and on each component template; use the narrowest one.
- **`nova-compute` is not here.** It runs on data plane nodes and is deployed
  by Ansible. After adding compute nodes, host discovery must run:
  `oc rsh -n openstack nova-cell0-conductor-0 nova-manage cell_v2 discover_hosts --verbose`
  (the lab script does it).
- **Inspect.** `oc get novaapi,novascheduler,novaconductor,novametadata -n openstack`.
  `nova` and `novacell` print only an `AGE` column: read their conditions with
  a `jsonpath` query.
- **Restart one component.** `oc delete pod -n openstack nova-scheduler-0`.

## Services not deployed by default

Horizon, Cinder, Swift, Barbican, Heat, Telemetry, Octavia, Designate, Manila
and Ironic are disabled in the lab manifest (reasons in the
[architecture](../architecture.md#software-layers)). Their operators are
installed all the same, so each can be enabled by a change of the control
plane CR.

- **Horizon** is the worked example:
  [Enable a service](../operations/05-enable-a-service.md) turns it on
  (a `Horizon` CR, a Deployment and a Route named `horizon` appear within
  about a minute) and off again.
- **Cinder and Swift** need a storage backend the lab does not have.
- **Telemetry** needs an image from a registry that requires a vendor account.

## OpenStackClient

| | |
|---|---|
| Operator | `openstack-operator` |
| CR | `OpenStackClient` |
| Workload | A single pod named `openstackclient` |

A ready-to-use admin CLI: `clouds.yaml` comes from the ConfigMap
`openstack-config`, the password from the Secret `openstack-config-secret`.

**[READ-ONLY]**

```bash
oc rsh -n openstack openstackclient openstack service list
```

It is the replacement for sourcing `admin-openrc.sh` on a controller.

---

## Quick reference

| Service | CR kind (`oc get ...`) | Workload type | Persistent data |
|---|---|---|---|
| Galera | `galera` | StatefulSet | Yes |
| RabbitMQ | `rabbitmq` | StatefulSet | Yes |
| Memcached | `memcached` | StatefulSet | No |
| DNS | `dnsmasq` | Deployment | No |
| Keystone | `keystoneapi` | Deployment | No |
| Placement | `placementapi` | Deployment | No |
| Glance | `glance`, `glanceapi` | StatefulSet | Yes (image store) |
| OVN | `ovndbcluster`, `ovnnorthd` | StatefulSet | Yes (databases) |
| Neutron | `neutronapi` | Deployment | No |
| Nova | `nova`, `novaapi`, `novascheduler`, `novaconductor`, `novacell`, `novametadata`, `novanovncproxy` | StatefulSet | No |

---

**Previous:** [Configuration, secrets and data](04-configuration-secrets-and-data.md) · **Next:** [Control plane and data plane](06-control-plane-and-data-plane.md)
