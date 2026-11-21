---
title: "The OKD node and OpenStack"
description: "In a Kolla deployment the controllers are the control plane: if a controller is down, its containers are down. Here the same is true one level removed."
---

# The OKD node and OpenStack

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) for every read-only command run on the bastion and on the node, and for the planned reboot of scenario B (executed and measured, and measured twice more on 2026-11-12 during MachineConfig rolls), `cordon` and a server-side dry run of `drain` (2026-11-12); not executed: the host cloud commands, a hard stop of the VM, a real `drain`, the approval of certificate requests (none was pending), the restart of `crio` and `kubelet`, and any degraded cluster operator (none occurred)

## In short

- Everything OpenStack runs on one OKD node: recover in a fixed order
  (VM, kubelet, etcd and API server, cluster operators, then OpenStack)
  and do not touch OpenStack pods while the platform is still settling.
- A planned reboot is a full control plane outage of about six minutes.
  Instances keep running. Cordon and drain add nothing on a single node.
- For about twenty seconds after the API returns, statuses are stale:
  wait for the node to pass `NotReady` then `Ready`.
- After any restart of the OKD node, check the OVN agents on each
  compute node and restart `edpm_ovn_controller` and
  `edpm_ovn_metadata_agent` if they are not connected.

In a Kolla deployment the controllers are the control plane: if a controller
is down, its containers are down. Here the same is true one level removed.
OpenStack services are pods; pods live on the OKD node; the node is a
virtual machine. On a single-node lab every OpenStack control plane service
shares the fate of that one node, and of the handful of OKD components that
make pods possible.

What OpenStack needs from OKD, bottom-up:

| OKD component | Namespace or operator | If it fails |
|---------------|-----------------------|-------------|
| Node (kubelet, CRI-O) | the VM itself | Nothing runs or restarts |
| etcd, kube-apiserver | `etcd`, `kube-apiserver` cluster operators | `oc` fails; operators cannot reconcile; running pods keep running |
| Pod network (OVN-Kubernetes), Multus | `network` cluster operator | Pods cannot talk to each other; new pods stay in `ContainerCreating` |
| Cluster DNS | `dns` cluster operator | Services cannot find each other by name |
| Ingress router | `ingress` cluster operator | Routes (public OpenStack endpoints, console) return errors |
| OLM | `operator-lifecycle-manager` cluster operators | Operators cannot be installed or upgraded; running ones are unaffected |

The compute nodes are **not** part of OKD. Instances keep running when the
OKD node is down; they just cannot be managed.

## Scenario A: node NotReady

### 1. Initial symptoms

- `oc get nodes` shows `NotReady`, or `oc` does not answer at all.
- Pods show `Unknown`, `Terminating` or stale statuses.
- All OpenStack APIs are unreachable.

### 2. Read-only investigation

From the bastion, as far as each step works:

**[READ-ONLY]**

```bash
ping -c 2 192.168.130.10
curl -sk -o /dev/null -w '%{http_code}\n' https://api.$(source lab.env; echo ${CLUSTER_NAME}.${BASE_DOMAIN}):6443/readyz
oc get nodes
oc describe node | sed -n '/Conditions:/,/Addresses:/p'
oc get clusteroperators
oc get events -A --sort-by=.lastTimestamp | tail -20
```

If the API does not answer, go to the node directly (the bastion holds the
key for user `core`):

**[READ-ONLY]**

```bash
ssh core@192.168.130.10
# On the node:
uptime; free -m; df -h /var
sudo systemctl is-active kubelet crio
sudo journalctl -u kubelet --since "15 min ago" --no-pager | tail -30
sudo crictl ps -a --state exited | head -20
sudo crictl ps | grep -E 'etcd|kube-apiserver'
```

On the lab the first `ssh` is refused with "REMOTE HOST IDENTIFICATION HAS
CHANGED": the bastion still knows the host key the address had during the
installation. Remove the old key once, then connect again:

**[CHANGE]** Edits `~/.ssh/known_hosts` on the bastion only.

```bash
ssh-keygen -R 192.168.130.10
```

In the journal the kubelet lines carry the identifier `kubenswrapper`, not
`kubelet`.

From the workstation, the view of the host cloud:

**[READ-ONLY]**

```bash
openstack server show okdlab-okd -c status -c power_state -c OS-EXT-STS:task_state
openstack console log show okdlab-okd | tail -40
```

### 3. Expected observations

Healthy reference on the lab: one node `Ready` with the roles
`control-plane,master,worker`, 34 cluster operators all `True False False`,
`kubelet` and `crio` active, no certificate request (`oc get csr` prints
"No resources found"). Two `installer-*` pods in `Error` in
`openshift-kube-controller-manager` and `openshift-kube-scheduler` are
leftovers of the installation and mean nothing.

| Observation | Cause |
|-------------|-------|
| API answers again after a restart, node shows `Ready`, pods show `Running`, but nothing works | Stale statuses: for about twenty seconds after the API server is back it shows the state from before the stop. The node then turns `NotReady` and `Ready` again. Wait a minute before concluding anything |
| VM `SHUTOFF` or `ERROR` in the host cloud | Stopped or failed outside the lab |
| VM active, no ping | Network of the VM, or the OS hung |
| Ping works, API does not answer, kubelet active | Control plane pods (etcd, API server) not running: often disk full, memory exhaustion, or expired certificates after a long shutdown |
| API answers, node `NotReady` with `KubeletNotReady` and a network message | Pod network not ready: CRI-O or Multus problem, typical after an unclean stop |
| Node `Ready`, several cluster operators degraded | The node is back but components are still recovering: wait, then look at the degraded ones |
| Node `Ready` with `MemoryPressure` or `DiskPressure` | [Resource exhaustion](resource-exhaustion.md), [storage](storage.md) |
| `oc get csr` shows `Pending` requests after a long shutdown | Kubelet certificates expired while the cluster was off |

### 4. Root cause

A single node concentrates every failure domain. The frequent causes on a
lab are the ones a lab invites: the VM was stopped abruptly, the lab was
shut down for weeks and certificates expired, or the disk or memory ran
out. Whatever the cause, the order of recovery is fixed: VM, kubelet, etcd
and API server, cluster operators, and only then OpenStack.

### 5. Resolution

VM stopped: start it from the workstation.

**[CHANGE]**

```bash
openstack server start okdlab-okd
```

Pending certificate requests after a long shutdown:

**[READ-ONLY]**

```bash
oc get csr
```

**[CHANGE]** Approves the node's certificate requests. Repeat until none is
pending (they come in two rounds).

```bash
oc get csr -o json | jq -r '.items[] | select(.status == {}) | .metadata.name' | xargs -r oc adm certificate approve
```

Kubelet or CRI-O stuck on the node:

**[CHANGE]** Restarts all pods on the node.

```bash
sudo systemctl restart crio kubelet
```

A node that stays `NotReady` after an unclean shutdown with CNI errors in
the kubelet log is a known problem on some OKD releases; the workaround is
release-specific, see
[OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md). It did
not occur on the lab with a clean reboot.

Then wait. After the clean reboot of scenario B everything was back in
under seven minutes; allow ten to twenty minutes after a cold start or an
unclean stop.

**[READ-ONLY]**

```bash
watch -n 10 'oc get nodes; oc get clusteroperators | awk "NR==1 || \$3!=\"True\" || \$5!=\"False\""'
```

Only when OKD is healthy, look at OpenStack, in dependency order: Galera
and RabbitMQ first ([runbook](galera-and-rabbitmq.md)), then the control
plane conditions.

### 6. Verification

**[READ-ONLY]**

```bash
oc get nodes
oc get clusteroperators
oc get openstackcontrolplane openstack
tests/smoke-test.sh
```

### 7. Risks and precautions

- Do not start fixing OpenStack pods while cluster operators are still
  recovering; most pod errors at that stage clear by themselves.
- Do not hard-reboot the VM as a first reaction: each unclean stop is a new
  risk for etcd, Galera and RabbitMQ.
- Take an etcd backup before experiments on the node
  ([backup and restore](../lifecycle/05-backup-and-restore.md)).

## Scenario B: planned node reboot

### 1. Initial symptoms

You need to reboot the node (configuration change, resize of the VM, kernel
update delivered by an OKD upgrade) and want to know what happens to
OpenStack.

### 2. Read-only investigation

Before:

**[READ-ONLY]**

```bash
oc get nodes
oc get clusteroperators | awk 'NR==1 || $3!="True" || $5!="False"'
oc get machineconfigpool
oc get openstackcontrolplane openstack
oc get pods -l app=galera
oc get pv | grep -c Bound
oc rsh openstackclient openstack server list --all-projects -c Name -c Status
```

### 3. Expected observations

- Everything is healthy before you start. Do not reboot a degraded cluster
  to "fix" it without knowing why it is degraded.
- With one node there is nowhere to move pods. A reboot is a full outage of
  the OpenStack control plane. Measured on the lab, from the reboot command
  (control plane and one compute node deployed, no instance running):

  | After | What happens |
  |-------|--------------|
  | 3 s | The API no longer answers |
  | 2 min 33 s | The node stops answering ping: until then it was stopping its pods cleanly |
  | 3 min 3 s | The node answers ping again |
  | 3 min 40 s | The API answers, with stale statuses: node `Ready`, pods `Running`, control plane `True`. `tests/smoke-test.sh` run at that moment reports 4 failed checks |
  | 4 min | The node is shown `NotReady`, the OpenStack pods `ContainerCreating` |
  | 4 min 15 s | Node `Ready`; pods start |
  | 5 min | Galera, memcached, OVN databases, Keystone and Glance are ready; RabbitMQ and the Nova services are still starting; `nova-scheduler` goes through `CrashLoopBackOff` (it started before RabbitMQ) |
  | 5 min 15 s | The control plane resource shows `False` for about half a minute |
  | 5 min 50 s | Control plane `True`, every service pod ready |
  | 6 min 35 s | The CronJob pods that were due during the outage have run; `tests/smoke-test.sh` reports 0 failed |

- No cluster operator was reported degraded at any time during the
  recovery, and no certificate request had to be approved.
- The two reboots of 2026-11-12 gave the same timeline; it is drawn as a
  sequence diagram in
  [OKD node maintenance](../knowledge-base/okd-node-maintenance.md#how-do-i-apply-a-machineconfig-on-the-single-node-and-what-happens-step-by-step).
- The pods are not replaced: the same pods come back with their restart
  counter increased by one (`nova-scheduler-0` by four). Galera was stopped
  cleanly and bootstrapped by itself ("Bootstrapping a new cluster", then
  "synced").
- The `nova-compute` service of the compute node reconnects without any
  action. `ovn_controller` reconnected alone on this first reboot, but
  **not** on the two reboots of 2026-11-12: it stayed `not connected`
  (`sudo podman exec ovn_controller ovn-appctl connection-status`), its
  container `unhealthy`, logging `connect: Address family not supported
  by protocol` for the southbound database every 8 seconds although the
  name resolved again, until it was restarted by hand 8 to 10 minutes
  later. Treat it like the metadata agent below.
- The OVN metadata agent of the compute node did **not** reconnect. The OVN
  southbound database was unreachable for about four minutes; the agent
  logged "continuing to reconnect in the background but suppressing further
  logging" and was still disconnected fifteen minutes later, with its unit
  `active` and its container `healthy`. `openstack network agent list`
  keeps showing it alive (`:-)`) until the next change in OVN (a new
  network or port), then shows `XXX`. This is why the smoke test passed
  right after the recovery and failed on "OVN agents alive" after the
  functional test. Observed on this reboot and on both reboots of
  2026-11-12 (three reboots of the OKD node alone out of three), and
  again for both agents on the start of the whole lab of 2026-11-14
  (dated tally in
  [Impact of OKD maintenance](../lifecycle/06-okd-maintenance-impact.md#4-explanation-what-recovers-by-itself-and-in-which-order)).
  That last time nobody restarted them and both reconnected by
  themselves, 15 and 16 minutes after their start; "did not
  reconnect" above therefore means "not within the 8 to 15 minutes
  it was watched". See the resolution below: the restart saves the
  wait.
- Instances on compute nodes keep running and keep their network
  connectivity (the OVN flows are already programmed on the compute node).
  New API calls fail until the control plane is back.

### 4. Root cause

What "cordon" and "drain" mean on a single node:

- `oc adm cordon` marks the node unschedulable: no new pod is placed on it.
  With one node, a pod that restarts while the node is cordoned stays
  `Pending`.
- `oc adm drain` evicts pods so they move elsewhere. There is no elsewhere:
  evicted pods of Deployments and StatefulSets become `Pending`. The lab
  declares no PodDisruptionBudget in the `openstack` namespace
  (`oc get pdb -n openstack`), so nothing there blocks a drain; the four
  budgets of the cluster belong to OKD components. On a single node, drain
  is mostly a way to stop workloads cleanly before the reboot, not a way to
  keep them available. It is not needed: after the reboot below, without
  cordon or drain, Galera and RabbitMQ came back alone. A server-side dry
  run (`oc adm drain <node> --dry-run=server --ignore-daemonsets
  --delete-emptydir-data`, 2026-11-12) listed 198 pods to evict, 83 of
  them in `openstack`, and no budget in the way. The Machine Config
  Operator itself skips the drain on a single-node control plane.
- While the node is cordoned the `master` MachineConfigPool shows
  `UPDATING=True` and no ready machine; it is the cordon, not a rollout.

What happens during the reboot: the kubelet has no shutdown grace period
on this lab and stops within a second; systemd then stops the containers
itself over about 2 min 30 (measured on 2026-11-12: RabbitMQ is killed at
once, several containers reach their stop timeout; Galera still restarted
alone with `safe_to_bootstrap: 1`), the node restarts, static pods (etcd, API server) come up,
then everything else in no particular order. OpenStack services that start
before their database retry until it is there; the operators drive Galera's
bootstrap ([runbook](galera-and-rabbitmq.md)).

Persistent data is on the node's disk and survives. Pod addresses change;
Service addresses, MetalLB addresses and Routes do not.

### 5. Resolution

A clean reboot through the node itself (not a hard reset in the host cloud):

**[CHANGE]** Full outage of the OpenStack control plane until recovery.

```bash
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc debug node/${node} -- chroot /host systemctl reboot
```

Then follow the recovery:

**[READ-ONLY]**

```bash
# Wait for the API to go away, then to come back.
while oc get --raw /readyz >/dev/null 2>&1; do sleep 5; done
until oc get --raw /readyz >/dev/null 2>&1; do sleep 5; done
sleep 60    # the first statuses are stale
until oc get nodes 2>/dev/null | grep -qw Ready; do sleep 10; done
oc get clusteroperators | awk 'NR==1 || $3!="True" || $5!="False"'
oc get pods -n openstack -w
```

Do not test for `Ready` immediately after the command: the node is still
shown `Ready` while it shuts down and again when the API comes back.

Then check the agents of the compute nodes, after having created anything
in Neutron (the functional test does):

**[READ-ONLY]**

```bash
oc rsh openstackclient openstack network agent list
```

**[READ-ONLY]** On each compute node; the agent list alone can lie until
the next change in OVN.

```bash
sudo podman exec ovn_controller ovn-appctl connection-status
```

**[CHANGE]** On each compute node whose agents are shown `XXX` or whose
controller is `not connected`. Restart both: connected in less than ten
seconds, both agents alive within thirty seconds on the lab. Running
instances keep their connectivity.

```bash
sudo systemctl restart edpm_ovn_controller edpm_ovn_metadata_agent
```

If you cordoned the node beforehand, uncordon it or nothing will start:

**[CHANGE]**

```bash
oc adm uncordon ${node}
```

For a longer stop (shutting the lab down for days), follow
[OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md) and
take a backup first
([backup and restore](../lifecycle/05-backup-and-restore.md)): a long stop
adds the certificate considerations.

### 6. Verification

**[READ-ONLY]**

```bash
oc get nodes
oc get clusteroperators | awk 'NR==1 || $3!="True" || $5!="False"'
oc get openstackcontrolplane openstack
oc get pods -n openstack | grep -v 'Running\|Completed' || true
tests/smoke-test.sh --functional
tests/smoke-test.sh
```

The second run matters: it checks the OVN agents after the functional test
has changed something in OVN.

### 7. Risks and precautions

- Stop API activity first: an instance build or migration interrupted by the
  reboot is left in a transitional state.
- Never combine a node reboot with a pending OpenStack change.
- A `MachineConfig` change or an OKD upgrade reboots the node on its own
  schedule (10 to 15 seconds after the change, measured; see
  [OKD node maintenance](../knowledge-base/okd-node-maintenance.md)). On a single node that is an unannounced OpenStack outage: check
  `oc get machineconfigpool` and plan it.
- Forgetting `uncordon` is the classic cause of "everything is Pending after
  the reboot".

## Scenario C: a cluster operator is degraded

### 1. Initial symptoms

- `oc get clusteroperators` shows `DEGRADED=True` or `AVAILABLE=False` for
  one or more operators.
- OpenStack may or may not be affected.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get clusteroperators
oc describe clusteroperator <name> | sed -n '/Conditions:/,/Extension:/p'
oc get clusterversion
oc get pods -A | grep -v 'Running\|Completed' | head -30
oc get machineconfigpool
```

### 3. Expected observations

Use the table at the top of this page to judge the impact on OpenStack:
`network`, `dns`, `ingress`, `etcd` and `kube-apiserver` matter immediately;
`console`, `monitoring`, `image-registry`, `openshift-samples` and
`insights` do not affect OpenStack at all.

On OKD, a few operators can report degraded for reasons specific to the
community distribution (for example sample image streams that reference a
registry requiring a subscription). Those are cosmetic for this lab. None
was degraded on the lab, neither after the installation nor after the node
reboot, so this scenario was only validated for its commands.

### 4. Root cause

Cluster operators are to OKD what the OpenStack operators are to OpenStack:
each manages one platform component and reports its state in conditions.
The same reading method applies: find the condition that is not as
expected, read its message, then look at the pods of that operator's
namespace.

### 5. Resolution

Depends on the operator; start from the message. The component's pods live
in a namespace named `openshift-<component>`:

**[READ-ONLY]**

```bash
oc get pods -n openshift-ingress
oc get pods -n openshift-dns
oc get pods -n openshift-ovn-kubernetes
oc logs -n openshift-<component> <pod> --tail=50
```

Deeper OKD troubleshooting is the subject of the OKD administration part of
the documentation.

### 6. Verification

**[READ-ONLY]**

```bash
oc get clusteroperators | awk 'NR==1 || $3!="True" || $5!="False"'
```

### 7. Risks and precautions

- Do not edit objects in `openshift-*` namespaces by hand: they are managed
  by cluster operators and revert, exactly like OpenStack objects.
- Do not start an OKD upgrade while any cluster operator is degraded, and
  never during OpenStack maintenance.
