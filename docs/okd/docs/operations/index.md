# Operating OpenStack on OKD (Day 2)

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

This guide covers the daily work of an OpenStack operator once the lab is
deployed: looking at health, reading logs, restarting, reconfiguring, enabling
and scaling services. It assumes you know OpenStack well and Kubernetes little.
If a term is unfamiliar, the [concepts guide](../concepts/README.md) explains it.

When something is broken rather than merely to be changed, go to the
[troubleshooting runbooks](../troubleshooting/README.md).

## Reading order

| # | Document | You learn to |
|---|----------|--------------|
| 1 | [Inspect service status](01-inspect-service-status.md) | Walk the health chain from the control plane resource down to the API |
| 2 | [Logs](02-logs.md) | Find the right log for a service, an operator, a job, a compute node |
| 3 | [Restart a service](03-restart-a-service.md) | Restart safely, and know what a restart does not fix |
| 4 | [Change service configuration](04-change-service-configuration.md) | Edit `customServiceConfig` and follow the rollout |
| 5 | [Enable a service](05-enable-a-service.md) | Turn Horizon on and off |
| 6 | [Scale a service](06-scale-a-service.md) | Change replica counts, and when not to |
| 7 | [Passwords and secrets](07-passwords-and-secrets.md) | Read credentials, understand what rotation implies |
| 8 | [Data plane changes](08-dataplane-changes.md) | Re-run Ansible on compute nodes after a change |
| 9 | [Safe change checklist](09-safe-change-checklist.md) | Apply any change with a way back |

## Conventions

All commands run on the bastion, as the user that owns the kubeconfig. Unless
stated otherwise they target the `openstack` namespace; set it once:

**[CHANGE]** (changes only your local client context)

```bash
oc project openstack
```

Every command block carries one of three labels:

| Label | Meaning |
|-------|---------|
| **[READ-ONLY]** | Reads state. Safe at any time, including during an incident. A read-only block may write a file on the bastion or start a short-lived helper pod (`oc debug node/...`, which runs a privileged pod on the node only for the duration of the command); it never changes a lab resource. |
| **[CHANGE]** | Modifies the platform in a way that can be reverted. Read the risks first. |
| **[DESTRUCTIVE]** | Deletes data or state that cannot be recovered by reverting the command. |

Every scenario uses the same seven sections: initial symptoms, read-only
investigation, expected observations, root cause, resolution, verification,
risks and precautions. In the operations guide the "symptom" is usually a
need ("I want debug logs"), and the "root cause" section explains the
mechanism that makes the procedure work.

## The one rule

**Change the `OpenStackControlPlane` resource, nothing below it.** Deployments,
StatefulSets, ConfigMaps, Secrets with generated configuration and the
per-service custom resources (`KeystoneAPI`, `NovaAPI`, ...) are all outputs
of an operator. Editing them by hand is either reverted within a second or,
worse, silently kept until the next reconciliation overwrites it. See
[manual changes reverted](../troubleshooting/manual-changes-reverted.md).

It is the same discipline as never editing `/etc/kolla/<service>/` on a
controller: the files are generated, the source of truth is elsewhere.

## Daily toolkit

**[READ-ONLY]**

```bash
# The whole control plane in one line, then its per-service conditions.
oc get openstackcontrolplane            # short names: oscp, osctlplane
oc get oscp openstack -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}'

# Everything that runs.
oc get pods
oc get pods -o wide --sort-by=.status.startTime
oc get deployments,statefulsets,jobs,cronjobs

# One object in detail: spec, status, and the events at the bottom.
oc describe pod <pod>

# What happened recently in the namespace, oldest first.
oc get events --sort-by=.lastTimestamp

# Logs (see 02-logs.md).
oc logs <pod> [-c <container>] [--previous] [-f]

# The OpenStack CLI, already authenticated as admin.
oc rsh openstackclient openstack endpoint list
oc rsh openstackclient                      # interactive shell

# Data plane.
oc get openstackdataplanenodeset            # short name: osdpns
oc get openstackdataplanedeployment         # short name: osdpd
```

### Which resource and which operator own this pod?

Kubernetes records ownership in `metadata.ownerReferences`. Walk it upwards:

**[READ-ONLY]**

```bash
pod=keystone-xxxxxxxxxx-yyyyy   # any pod name

# 1. Pod -> ReplicaSet, StatefulSet, DaemonSet or Job
oc get pod "${pod}" -o jsonpath='{range .metadata.ownerReferences[*]}{.kind}/{.name}{"\n"}{end}'

# 2. Repeat on the owner until the kind is an OpenStack one
oc get replicaset <name> -o jsonpath='{range .metadata.ownerReferences[*]}{.kind}/{.name}{"\n"}{end}'
oc get deployment keystone -o jsonpath='{range .metadata.ownerReferences[*]}{.apiVersion} {.kind}/{.name}{"\n"}{end}'
```

On the lab the three commands print, in order:

```text
ReplicaSet/keystone-7b45c49ccb
Deployment/keystone
keystone.openstack.org/v1beta1 KeystoneAPI/keystone
```

The API group of the last hop (`keystone.openstack.org`) names the operator:
its controller runs in the `openstack-operators` namespace as the Deployment
`keystone-operator-controller-manager`.

**[READ-ONLY]**

```bash
oc -n openstack-operators get deployments
oc -n openstack-operators get deployments | grep -i keystone
oc -n openstack-operators get pods -l openstack.org/operator-name=keystone
```

There is one `<service>-operator-controller-manager` Deployment per service
operator (22 Deployments in total, including the operators of services the
lab does not enable). Two groups have no Deployment of their own:
`placement.openstack.org` is served by the nova operator, and
`rabbitmq.openstack.org`, `memcached.openstack.org` and
`network.openstack.org` by the infra operator.

The `KeystoneAPI/keystone` resource is itself owned by
`OpenStackControlPlane/openstack`, which is the object you edit.

Shortcut: most service pods carry a `service=<name>` label. The values on
the lab are `keystone`, `placement`, `glance`, `neutron`, `nova-api`,
`nova-scheduler`, `nova-conductor`, `nova-metadata`, `nova-novncproxy`,
`openstack-galera`, `openstack-cell1-galera`, `memcached`, `dnsmasq`,
`ovn-northd`, `ovsdbserver-nb`, `ovsdbserver-sb` and `openstackclient`.
The RabbitMQ pods are the exception: they have no `service` label and are
selected with `app.kubernetes.io/name`.

**[READ-ONLY]**

```bash
oc get pods -L service
oc get pods -l service=keystone
oc get pods -l app.kubernetes.io/name=rabbitmq
oc get pods -l app=galera
```
