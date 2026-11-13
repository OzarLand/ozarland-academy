# Operating OpenStack on OKD (Day 2)

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

**Start here** once the lab is deployed and the smoke test passes. This
guide covers the daily work of an OpenStack operator: looking at health,
reading logs, restarting, reconfiguring, enabling and scaling services. It
assumes you know OpenStack well and Kubernetes little.

Read pages 1 and 2 first: they are read-only and every other page relies on
them. The other pages can be read in any order; page 9 is the checklist to
keep open during any change.

When something is broken rather than merely to be changed, go to the
[troubleshooting runbooks](../troubleshooting/README.md).

## In short

- Change the `OpenStackControlPlane` resource, nothing below it
  ([the one rule](#the-one-rule)).
- There is no "reconfigure" command: saving the resource is the trigger,
  and the result arrives seconds to minutes later, in conditions.
- The control plane reconciles continuously. Compute nodes change only
  when you create a data plane deployment.
- A `True` control plane means "what was asked is done", not "the API
  answers": finish every change with a call to the API.
- Every command block is labelled **[READ-ONLY]**, **[CHANGE]** or
  **[DESTRUCTIVE]** ([conventions](#conventions)).

## Prerequisites

| Prerequisite | Where |
|---|---|
| The lab is deployed and `tests/smoke-test.sh` passes | [Installation, step 7](../installation/07-verification.md) |
| A shell on the bastion, in the repository directory, with `oc project openstack` done | [Conventions](#conventions) |
| The vocabulary: operator, custom resource, condition, reconciliation | [Concepts guide](../concepts/README.md) |

## Pages

The last column is the duration of the example change of the page, as
measured on the lab; the pages give the details.

| # | Page | You learn to | Measured on the lab |
|---|------|--------------|---------------------|
| 1 | [Inspect service status](01-inspect-service-status.md) | Walk the health chain from the control plane resource down to the API | Read-only |
| 2 | [Logs](02-logs.md) | Find the right log for a service, an operator, a job, a compute node | Read-only; a must-gather collection takes about 2 min 30 s |
| 3 | [Restart a service](03-restart-a-service.md) | Restart safely, and know what a restart does not fix | 20 to 60 s per pod |
| 4 | [Change service configuration](04-change-service-configuration.md) | Edit `customServiceConfig` and follow the rollout | About 35 s (Keystone) |
| 5 | [Enable a service](05-enable-a-service.md) | Turn Horizon on and off | About 50 s to enable, 30 s to disable |
| 6 | [Scale a service](06-scale-a-service.md) | Change replica counts, and when not to | About 30 s up, 3 s down |
| 7 | [Passwords and secrets](07-passwords-and-secrets.md) | Read credentials, understand what rotation implies | About 25 s of rollout (Placement) |
| 8 | [Data plane changes](08-dataplane-changes.md) | Re-run Ansible on compute nodes after a change | 2 min 30 s (`nova` only) to about 14 min (full run on a deployed node) |
| 9 | [Safe change checklist](09-safe-change-checklist.md) | Apply any change with a way back | Read-only checks before and after |

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
mechanism that makes the procedure work. Each page starts with an "In
short" block: read it first, and again before applying the procedure.

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

---

**Previous:** [Installation guide](../installation/README.md) · **Next:** [Inspect service status](01-inspect-service-status.md) · **See also:** [Lifecycle management](../lifecycle/README.md)
