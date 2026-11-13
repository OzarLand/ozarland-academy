# From Kolla-Ansible to operators

> Status: aligned with the lab deployed on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); explanatory page, commands spot-checked against the validated guides

## In short

- OpenStack itself does not change: same services, same options, same APIs.
  What changes is **who assembles the platform and who keeps it running**.
- With Kolla-Ansible you run a tool from a deployment host. Here you
  **declare** the platform as objects in the Kubernetes API, and programs
  called operators make reality match them, all the time.
- The `OpenStackControlPlane` custom resource replaces `globals.yml`: the
  durable way to change anything is to edit that object.
- A manual fix on an object managed by an operator does not last.
- Compute nodes are the exception: they are still configured by Ansible over
  SSH, on demand.

You already know what an OpenStack control plane is made of. This document
maps what you do today with Kolla-Ansible onto the operator model.

## The one-paragraph summary

With Kolla-Ansible, *you* run a tool from a deployment host. The tool reads
`globals.yml`, `passwords.yml` and the inventory, renders configuration files,
and starts containers on hosts over SSH. Between two runs nothing watches the
platform: if a container is removed by hand it stays removed until someone runs
`kolla-ansible deploy` again.

With operators, you **declare** the platform as objects stored in the
Kubernetes API. Programs called operators run permanently inside the cluster,
watch those objects, and continuously make reality match them. There is no
deployment host and no "run": saving the object *is* the deployment, and the
correction loop never stops.

## Translation table

The right-hand column uses Kubernetes object types (Pod, Deployment,
StatefulSet, Secret, Service, Route, Job). Each one is explained, with its
Kolla equivalent, in
[Kubernetes building blocks](02-kubernetes-building-blocks.md). A *custom
resource* (CR) is an object of a type that an operator adds to the Kubernetes
API; see
[Operators, CRDs and reconciliation](03-operators-crds-and-reconciliation.md).

| Kolla-Ansible | Operator model in this lab | Notes |
|---|---|---|
| Deployment host with `kolla-ansible` installed | The OKD cluster itself, plus `oc` on the bastion | The logic lives in the operators, not on a deployment host |
| `globals.yml` | The `OpenStackControlPlane` custom resource (CR) | One YAML object describing which services are enabled and how |
| `/etc/kolla/config/<service>/*.conf` overrides | `customServiceConfig` (and `defaultConfigOverwrite`) fields inside the CR | An oslo.config snippet layered on top of the generated configuration |
| `passwords.yml` | The `osp-secret` Kubernetes Secret | Referenced from the CR by `spec.secret` |
| Inventory groups (`control`, `network`, `compute`) | For the control plane: the Kubernetes scheduler and `nodeSelector`. For compute nodes: `OpenStackDataPlaneNodeSet` | Control plane pods are scheduled; they are not pinned to a host by an inventory |
| A Kolla container (`nova_api`) | A container inside a Pod (`nova-api-0`) | Several closely related containers can share one pod |
| `docker ps` / `podman ps` | `oc get pods -n openstack` | |
| `docker logs nova_api` | `oc logs -n openstack nova-api-0 -c nova-api-api` | `nova-api-0` has two containers, `nova-api-api` and `nova-api-log`; list them with `oc get pod <pod> -o jsonpath='{.spec.containers[*].name}'` |
| `docker exec -it nova_api bash` | `oc rsh -n openstack nova-api-0` | |
| `docker restart nova_api` | `oc delete pod` (the Deployment or StatefulSet recreates it) | Not `oc rollout restart`: the operator reverts it. See [Restart a service](../operations/03-restart-a-service.md) |
| `kolla-ansible genconfig` | The service operator renders configuration into a Secret | Automatic, on every change of the CR |
| `kolla-ansible reconfigure` | Reconciliation | Automatic and continuous; you only edit the CR |
| `kolla-ansible deploy --tags nova` | Not needed; each service operator reconciles its own CR | |
| `kolla-ansible bootstrap-servers` / `prechecks` | For compute nodes: the first data plane services (`bootstrap`, `configure-network`, `validate-network`...) run as Ansible jobs | |
| HAProxy + keepalived VIP | Kubernetes `Service` (load balancing to pods), OKD `Route` (public HTTPS entry), MetalLB (the internal VIP on the internalapi network) | No HAProxy container to manage |
| MariaDB container + `mariadb_recovery` | `Galera` CR managed by `mariadb-operator` | Bootstrap after a full stop is automated by the operator |
| `kolla_toolbox`, admin `openrc` | The `openstackclient` pod | `oc rsh -n openstack openstackclient` |
| `kolla-ansible upgrade` | `OpenStackVersion` CR (`spec.targetVersion`) | Operator upgrade and service image update are two separate steps; see [lifecycle](../lifecycle/README.md) |
| `kolla-ansible pull` / `openstack_release` + registry | Image references held by the `OpenStackVersion` CR | Individual images can be overridden with `customContainerImages` |
| `kolla-ansible deploy --limit compute01` | `OpenStackDataPlaneDeployment` CR (optionally with `ansibleLimit` or `servicesOverride`) | This part of the model is still Ansible over SSH; see [data plane changes](../operations/08-dataplane-changes.md) |
| `/var/log/kolla/<service>/` | Container standard output, read with `oc logs` | On compute nodes: journald and podman; see [Logs](../operations/02-logs.md) |
| `kolla-ansible mariadb_backup` | `GaleraBackup` CR | |

## What stays exactly the same

- **OpenStack itself.** Keystone, Nova, Neutron and Glance are the same
  code, with the same configuration options, the same APIs, the same database
  schemas and the same RabbitMQ usage. `openstack server list` behaves the same.
- **Configuration semantics.** A `[DEFAULT] debug = true` snippet means what it
  has always meant. Only the delivery mechanism changes.
- **Containers.** Services still run in containers built from RDO packages. On
  compute nodes they even still run under podman and systemd, without Kubernetes.
- **Architecture knowledge.** Cells, placement, OVN northbound/southbound,
  Galera quorum, RabbitMQ queues: your troubleshooting instincts remain valid.
  The OpenStack-level diagnosis is unchanged; the Kubernetes layer is an extra
  place to look *before* you reach it.

## What changes in daily work

### You edit objects, not files on hosts

There is no `/etc/kolla` to edit. The source of truth is the
`OpenStackControlPlane` CR named `openstack` in the cluster, rendered from
`deployment/openstack/controlplane/openstackcontrolplane.yaml.tmpl`.

**[READ-ONLY]**

```bash
oc get openstackcontrolplane -n openstack
oc get openstackcontrolplane openstack -n openstack -o yaml | less
```

A change is made by modifying that object. The service operator notices,
renders new configuration, and rolls the affected pods:

**[CHANGE]** Restarts the Keystone pod (a short API outage with one replica).

```bash
oc patch openstackcontrolplane openstack -n openstack --type=merge -p '
spec:
  keystone:
    template:
      customServiceConfig: |
        [DEFAULT]
        debug = true
'
```

The complete, validated procedure (including how to revert) is
[Change service configuration](../operations/04-change-service-configuration.md).

### The platform repairs itself, including against you

If you delete a Keystone pod, a new one is created at once and is ready after
about half a minute. If you edit the generated configuration Secret or the
Keystone `Deployment` by hand, the operator puts it back within a second.

This is the biggest behavioural difference with Kolla:
**manual fixes on managed objects do not last**. The durable fix is always a
change to the CR. The mechanics are explained in
[Why manual edits of managed objects do not stick](03-operators-crds-and-reconciliation.md#why-manual-edits-of-managed-objects-do-not-stick).

### Health is read from status conditions

Instead of checking that containers are `Up`, you read the conditions that each
operator writes into the `status` of its CR:

**[READ-ONLY]**

```bash
oc get openstackcontrolplane openstack -n openstack \
  -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}'
```

A condition that is `False` names the layer that is blocked (input Secret
missing, database not ready, deployment not ready...). This is usually a faster
entry point than logs.

### Two kinds of "is it running?"

There are now two inventories of the same service, and you will use both:

| Question | Where to ask | Example |
|---|---|---|
| Is the process running, on which node, how many restarts? | Kubernetes | `oc get pods -n openstack -l service=nova-api -o wide` |
| Is the service registered and reporting in OpenStack? | OpenStack | `openstack compute service list` |

The two views can disagree:

- A pod can be `Running` while the OpenStack service is `down` (for example,
  RabbitMQ unreachable).
- Conditions can all be `True` while an API answers 503 (seen on the lab
  after a password change, see
  [Passwords and secrets](../operations/07-passwords-and-secrets.md)).

Check Kubernetes first, then OpenStack.

### Hosts matter less for the control plane, and as much as before for compute

Control plane pods are placed by the Kubernetes scheduler. On the single-node
lab they all land on the same node, but nothing in the CR says so.

Compute nodes are different: they are outside the cluster, they are listed
explicitly in an `OpenStackDataPlaneNodeSet`, and they are configured by
Ansible playbooks (the `edpm-ansible` collection) launched as Kubernetes Jobs
(pods that run once, to completion). That half of the platform will feel
familiar. See
[Control plane and data plane](06-control-plane-and-data-plane.md).

### Upgrades are split in two

Kolla ties tool version and OpenStack release together. Here:

1. Upgrading the **operators** changes the controllers and makes new service
   images *available*. It goes through the Operator Lifecycle Manager (OLM),
   the OKD component that installs operators from a catalog, much like a
   package manager; see
   [OKD in brief](07-okd-in-brief.md#operator-lifecycle-manager).
2. Updating the **services** happens only when you set
   `spec.targetVersion` on the `OpenStackVersion` CR.

No downgrade path exists upstream for either step. Treat both as one-way
operations and take backups first; what the lab could and could not verify is
in [Rollback limitations](../lifecycle/04-rollback-limitations.md).

## A first tour of the lab

**[READ-ONLY]**

```bash
# The operators: one controller-manager pod per service operator
oc get pods -n openstack-operators

# The declared control plane and its overall readiness
oc get openstackcontrolplane -n openstack

# The service-level CRs created from it
oc get keystoneapi,galera,rabbitmq,memcached,glance,neutronapi,nova,ovndbcluster -n openstack

# The resulting workloads and pods
oc get deployments,statefulsets -n openstack
oc get pods -n openstack

# OpenStack's own view
oc rsh -n openstack openstackclient openstack endpoint list
oc rsh -n openstack openstackclient openstack compute service list
```

---

**Previous:** [Concepts index](README.md) · **Next:** [Kubernetes building blocks](02-kubernetes-building-blocks.md)
