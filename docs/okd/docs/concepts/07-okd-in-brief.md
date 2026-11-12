# OKD in brief

> Status: aligned with the lab deployed on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); explanatory page, commands spot-checked against the validated guides

This document contains the minimum you need to know about OKD in order to
operate OpenStack on it (phases 1 to 3 of the learning roadmap). It is
intentionally short. Cluster networking, storage, scheduling, monitoring and
OKD upgrades in depth belong to Phase 4.

Command blocks are **[READ-ONLY]** unless labelled otherwise.

## What OKD is

OKD is the community distribution of Kubernetes that Red Hat OpenShift is built
from. Compared with plain Kubernetes it adds, already integrated:

| Addition | Why it matters for this lab |
|---|---|
| An immutable node operating system (CentOS Stream CoreOS, "SCOS") managed by the cluster | You do not `dnf install` or edit files on nodes |
| Cluster operators that manage the platform itself | The cluster's own health is read the same way as OpenStack's |
| Operator Lifecycle Manager (OLM) | It installs and upgrades the OpenStack operators |
| Routes and an ingress router | Public OpenStack endpoints |
| Multus and OVN-Kubernetes networking | Secondary networks for pods |
| Security Context Constraints (SCC) | Why some pods are refused |
| The `oc` CLI and a web console | Daily tools |

The lab is a **single-node** cluster: one machine is at the same time the
Kubernetes control plane and the only worker. There is no redundancy; a node
reboot is a full outage of the OpenStack control plane (about six minutes on
the lab, see [OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md)).

## `oc` and `kubectl`

`oc` is a superset of `kubectl`. Every `kubectl` command works identically with
`oc`; `oc` adds OKD-specific commands. Documentation written for `kubectl`
applies unchanged.

| `oc` addition | Purpose |
|---|---|
| `oc project <ns>` | Set the default namespace |
| `oc rsh <pod>` | Shell into a pod (shorthand for `exec -it ... sh`) |
| `oc debug node/<node>` | Root shell on a node through a temporary privileged pod |
| `oc adm ...` | Administrative commands (`must-gather`, `upgrade`, `top`, `certificate approve`) |
| `oc get routes`, `oc get clusteroperators` | OKD resource types |

Authentication uses a `kubeconfig` file produced by the installer; the lab
installs it as `~/.kube/config` on the bastion. It grants full administrative
access: treat it like a root password and keep it out of Git.

```bash
oc whoami
oc get nodes -o wide
oc version
```

## Is the cluster itself healthy?

Before investigating OpenStack, spend ten seconds on the layer underneath.

```bash
oc get nodes                      # STATUS Ready
oc get clusterversion             # installed OKD version, upgrade in progress?
oc get clusteroperators           # AVAILABLE=True, PROGRESSING=False, DEGRADED=False
oc adm top node                   # CPU and memory actually used
oc get pods -A | grep -Ev 'Running|Completed'   # anything unhealthy, cluster-wide
```

**Cluster operators** are to OKD what the service operators are to OpenStack:
one per platform function (`kube-apiserver`, `etcd`, `network`, `ingress`,
`dns`, `machine-config`, `storage`...; 34 on the lab), each reporting
conditions. A degraded
`ingress` operator explains unreachable public OpenStack endpoints; a degraded
`network` or `dns` operator explains almost anything.

```bash
oc describe clusteroperator ingress
```

## Namespaces you will meet

| Namespace | Content |
|---|---|
| `openstack`, `openstack-operators` | The subject of this lab |
| `cert-manager` | Certificate issuance (installed from the upstream release manifest) |
| `metallb-system` | MetalLB (`controller` and `speaker`) |
| `openshift-ingress` | The router pods serving Routes |
| `openshift-ovn-kubernetes`, `openshift-multus` | Cluster networking (not the OpenStack OVN) |
| `openshift-etcd`, `openshift-kube-apiserver` | Kubernetes control plane |
| `openshift-machine-config-operator` | Node configuration |
| `openshift-operator-lifecycle-manager`, `openshift-marketplace` | OLM and operator catalogs |
| `openshift-monitoring` | Built-in Prometheus and Alertmanager |

Everything named `openshift-*` is managed by a cluster operator: the "write at
the top, read everywhere" rule applies there too.

## Nodes are appliances

SCOS nodes are immutable and managed by the **Machine Config Operator**.
Node-level settings (kernel arguments, files under `/etc`, systemd units) are
declared in `MachineConfig` objects. Applying one makes the operator rewrite
the node configuration and **reboot the node**.

```bash
oc get machineconfigpool          # UPDATED / UPDATING / DEGRADED per pool
oc get machineconfig
```

For this lab it means:

- Do not hand-edit files on the node; changes are overwritten or flag the node
  as degraded.
- Anything that produces a new MachineConfig (some operators, some network
  configuration, an OKD upgrade) reboots the single node, hence a temporary
  outage of the OpenStack control plane. Running instances on the compute node
  keep running, but no API is available meanwhile. A MachineConfig change was
  not exercised on the lab; a plain node reboot was.

Access to a node for diagnosis. The command starts a temporary privileged pod
on the node; what you do inside decides whether it stays read-only:

```bash
oc debug node/okd-0
# inside the debug pod:
chroot /host
crictl ps | head            # containers as seen by the node's container runtime
journalctl -u kubelet --since '10 min ago' --no-pager | tail
```

`crictl` on an OKD node is the counterpart of `docker ps` on a Kolla
controller, but you rarely need it: `oc` shows the same information.

## Operator Lifecycle Manager

OLM installs operators from **catalogs** and keeps them upgraded. Four object
types are involved:

| Object | Role | Analogy |
|---|---|---|
| `CatalogSource` | A container image that indexes available operators and versions | A package repository |
| `Subscription` | "Keep operator X installed from that catalog, on this channel" | An installed package with auto-update settings |
| `InstallPlan` | A concrete set of changes OLM wants to apply; needs approval when the Subscription is `Manual` | A pending transaction |
| `ClusterServiceVersion` (CSV) | One installed version of an operator, with its status | The installed package version |

```bash
oc get catalogsource -A
oc get subscription,installplan,csv -n openstack-operators
```

The lab sets `installPlanApproval: Manual` on the OpenStack operator's
Subscription, so that an operator upgrade happens only when you approve the
InstallPlan. The deployment script approves the first one only.

Remember the two-step model: approving an InstallPlan upgrades the
**operators**; the OpenStack **service** images change only when you set
`targetVersion` on the `OpenStackVersion` CR. What the lab observed (no newer
bundle was offered, so no real operator upgrade took place) is in
[Operator upgrade](../lifecycle/02-operator-upgrade.md) and
[Minor update](../lifecycle/01-openstack-version-and-minor-update.md).

## Routes and DNS

A Route publishes a Service through the ingress router under
`<name>-<namespace>.apps.<cluster-domain>`. Three DNS names make a cluster
usable:

| Name | Used by |
|---|---|
| `api.<cluster-domain>` | `oc`, and anything calling the Kubernetes API |
| `api-int.<cluster-domain>` | The node itself |
| `*.apps.<cluster-domain>` | Every Route, therefore every public OpenStack endpoint |

In the lab the three names are served by dnsmasq on the bastion and are only
resolvable from the lab networks. If that DNS stops, `oc` and the public
endpoints fail while everything is healthy inside the cluster
([DNS and routing](../troubleshooting/dns-and-routing.md)). Inside the
cluster, services talk to each other through Service names
(`<svc>.<namespace>.svc`), served by the cluster's own DNS.

## Security Context Constraints

OKD refuses by default to run containers as root or with host access. An SCC is
the policy that says what a pod's service account may request (`restricted`,
`anyuid`, `privileged`...). The OpenStack operators create the service accounts
and bindings their workloads need, so you normally do nothing.

You meet SCCs only in failure cases: a pod that is never created, with an event
such as `unable to validate against any security context constraint`. Look at
the events of the owning ReplicaSet or StatefulSet:

```bash
oc get events -n <namespace> --sort-by=.lastTimestamp | grep -i 'security context'
oc get pod <pod> -n <namespace> -o jsonpath='{.metadata.annotations.openshift\.io/scc}{"\n"}'
```

This matters mostly when installing third-party components from upstream
manifests written for plain Kubernetes: the lab grants `privileged` to the
MetalLB speaker and `nonroot-v2` to its controller for this reason
([platform services](../installation/03-platform-services.md)).

## OKD versus Red Hat OpenShift: what affects this lab

| Topic | OKD | Consequence here |
|---|---|---|
| Node OS | CentOS Stream CoreOS | None for operations |
| Pull secret | No Red Hat subscription; a placeholder pull secret is enough to install | Images hosted on `registry.redhat.io` cannot be pulled |
| Operator catalogs | Community catalog only; Red Hat's certified operator catalog is not usable | cert-manager and MetalLB are installed from their upstream release manifests; node interfaces are configured at installation time, without the NMState operator |
| Storage operator | No packaged LVM Storage operator | The lab uses pre-created local volumes and the StorageClass `local-storage` |
| OpenStack operator | Upstream `openstack-k8s-operators` builds | Upstream is developed and tested against OpenShift, not OKD. What worked and what had to be adapted is in [versions and validation status](../versions.md) |
| Support and documentation | Community | OpenShift documentation is largely applicable, and so is the downstream documentation of the same OpenStack operators, with the caveats above |

One concrete example of the registry difference: Telemetry needs an image
hosted on a registry that requires a vendor account, so the lab disables it.
The alternative is to override that image in the `OpenStackVersion` CR
(`spec.customContainerImages`).

## Starting and stopping the lab cluster

A cluster is not a set of containers you can freeze at will:

- Internal certificates are rotated on a schedule, and the first ones issued
  at installation are valid 24 hours only: keep a new cluster running for its
  first day. After a long shutdown a node may come back with pending
  certificate signing requests to approve (`oc get csr`); after the short
  clean stop done on the lab there was none.
- Always shut the node down cleanly rather than powering off the virtual
  machine. An unclean stop was not tried on the lab.
- When the node returns, Kubernetes restarts everything, and the OpenStack
  operators reconcile: Galera bootstraps itself, then the services follow. On
  the lab the control plane was `True` again about three minutes after the
  virtual machine was started. Watching `oc get pods -n openstack -w` and the
  control plane conditions during a cold start is one of the most instructive
  exercises of the lab.

The procedure and its measurements are in
[OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md).

## Collecting diagnostics

**[CHANGE]** Starts a temporary namespace and collection pod, pulls an image,
and writes a local directory. Nothing in the OpenStack deployment is modified.

```bash
# OpenStack-specific bundle: CRs, logs and service state
oc adm must-gather --image=quay.io/openstack-k8s-operators/openstack-must-gather
```

On the lab the collection took about two and a half minutes and produced
about 70 MB. The archive contains configuration and may contain sensitive
data: review before sharing. See [Logs](../operations/02-logs.md).

## Where Phase 4 goes next

| Topic | Starting points |
|---|---|
| Cluster networking | OVN-Kubernetes, Services and kube-proxy replacement, NetworkPolicy, Multus, the ingress router |
| Storage | CSI drivers, StorageClasses, volume binding modes, reclaim policies |
| Scheduling and resources | Requests and limits, QoS classes, eviction, taints and tolerations, `nodeSelector` |
| Monitoring | The built-in Prometheus stack, alerts, `oc adm top`, events |
| Lifecycle | `oc adm upgrade`, cluster operator upgrade order, MachineConfig rollouts, etcd backup and restore, certificate rotation; start with [OKD upgrade](../lifecycle/07-okd-upgrade.md) |

Back to the [index](README.md).
