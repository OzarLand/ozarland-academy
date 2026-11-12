# Resource exhaustion

> Status: partially validated on the lab — every read-only command was run on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) and the figures below were measured; memory pressure, evictions and OOM kills were not provoked, because exhausting the only node risks etcd and the databases

The lab runs OKD and the whole OpenStack control plane on one 32 GB node.
That is enough, without much margin. On a Kolla controller, running out of
memory shows as the kernel OOM killer picking a process. Kubernetes adds two
earlier lines of defence, each with its own symptom, and one planning
mechanism (requests) that can refuse a pod while the node still has free
memory.

## 1. Initial symptoms

- Pods in `Evicted`, `OOMKilled`, or `Pending` with `Insufficient memory`.
- The node reports `MemoryPressure`.
- Everything is slow; API calls time out; `oc` itself is sluggish.
- Restart counts climbing on unrelated pods.

## 2. Read-only investigation

**[READ-ONLY]**

```bash
# Node conditions and actual usage.
oc describe node | sed -n '/Conditions:/,/Addresses:/p'
oc adm top node

# What is reserved (requests) versus what the node can allocate.
oc describe node | sed -n '/Allocatable:/,/System Info:/p;/Allocated resources:/,/Events:/p'

# Biggest consumers, cluster-wide and in OpenStack.
oc adm top pods -A --sort-by=memory | head -25
oc adm top pods -n openstack --containers --sort-by=memory | head -25
oc adm top pods -A --sort-by=cpu | head -15

# Casualties.
oc get pods -A --field-selector=status.phase=Failed
oc get pods -A -o json | jq -r '.items[] | . as $p | .status.containerStatuses[]? | select(.lastState.terminated.reason == "OOMKilled") | "\($p.metadata.namespace)/\($p.metadata.name) \(.name) restarts=\(.restartCount)"'
oc get events -A --sort-by=.lastTimestamp | grep -i 'evict\|oom\|insufficient\|pressure' | tail -20

# Requests and limits of one workload.
oc get pod <pod> -o json | jq '.spec.containers[] | {name, resources}'

# Kernel view on the node.
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc debug node/${node} --quiet -- chroot /host bash -c 'free -m; dmesg -T | grep -i "out of memory\|oom-kill" | tail -5; uptime'
```

## 3. Expected observations

Tell the three mechanisms apart:

| Symptom | Mechanism | Trigger |
|---------|-----------|---------|
| Pod `Pending`, event `Insufficient memory` or `Insufficient cpu` | Scheduler | Sum of **requests** would exceed the node's allocatable amount. Actual usage is irrelevant. |
| Container restarted, `Last State: OOMKilled`, exit code 137 | Kernel, per container | The container exceeded its own memory **limit**. |
| Pod `Evicted`, node `MemoryPressure=True` | Kubelet | Free memory on the node fell below the eviction threshold; the kubelet removes pods, starting with those using more than they requested. |
| `oom-kill` lines in `dmesg` for processes without a limit | Kernel, node-wide | The node ran out before the kubelet reacted. Anything can be killed. |

Measured on the healthy lab, with the default set of services and one
running instance:

- `oc adm top node`: about 21 GiB of memory used (69 %) and 12 % CPU. The
  memory **requests** add up to 72 % of the allocatable amount.
- On the node, `free -m` shows 32 GB in total, about 12 GB available and no
  swap.
- The largest consumers are OKD components, not OpenStack:
  `kube-apiserver` (3.4 GiB), `prometheus-k8s-0` (1.9 GiB), `ovnkube-node`
  (0.4 GiB), `kube-controller-manager` (0.4 GiB) and `etcd` (0.4 GiB).
- In the `openstack` namespace the API services lead: Neutron, Glance and
  Keystone use 430 to 500 MiB each. The infrastructure services are small:
  each Galera uses 90 to 150 MiB, each RabbitMQ about 150 MiB, and the OVN
  databases about 10 MiB.
- No pod is `OOMKilled` or evicted, and the kernel log has no `oom-kill`
  line.
- The `Failed` list is not empty on a fresh lab: it shows two leftovers of
  the installation, `installer-1-okd-0` in `openshift-kube-controller-manager`
  and `installer-3-okd-0` in `openshift-kube-scheduler` (the revision numbers
  vary). They are harmless.
- The kubelet evicts pods when less than 100 MiB of memory is available
  (`evictionHard`), and 1 GiB of memory and half a CPU are reserved for the
  system. The lab defines no `KubeletConfig`: these are the defaults.

To read the kubelet settings:

**[READ-ONLY]**

```bash
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc get --raw "/api/v1/nodes/${node}/proxy/configz" | jq '.kubeletconfig | {evictionHard, systemReserved, kubeReserved}'
```

## 4. Root cause

Requests and limits, in Kolla terms:

- A **request** is a reservation used only for placement. RabbitMQ requests
  1 CPU and 2Gi per instance by default; two instances reserve 4Gi even
  though they use 300 MiB together.
- A **limit** is a hard cap enforced by the kernel. On the lab only the two
  RabbitMQ pods have one (2 CPU, 2Gi). All the other OpenStack containers
  have neither request nor limit, so a leaking service is not killed alone:
  it pushes the whole node into pressure. It also means the scheduler does
  not count them: the 72 % of requests above come almost entirely from OKD
  itself, and enabling more OpenStack services never ends in `Pending`. The
  node fills up for real instead.

Common causes on the lab:

- Too many services enabled for 32 GB.
- API services scaled up, or worker counts raised through
  `customServiceConfig` (each worker is a Python process of a few hundred
  MiB).
- Many completed or failed pods and old Ansible runner pods are harmless for
  memory (the first data plane deployment alone leaves 15 of them in
  `Completed`), but a functional test loop or a must-gather adds real load.
- A cluster upgrade or a node reboot: everything starts at once and peaks.

## 5. Resolution

Reduce demand, largest and least critical first.

Disable what you do not use:

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"horizon":{"enabled":false}}}'
```

Return scaled services to one replica:

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"keystone":{"template":{"replicas":1}}}}'
```

Lower API worker counts through `customServiceConfig` (see the
[configuration guide](../operations/04-change-service-configuration.md)).

Clean up finished pods (they hold no memory, but clear the view):

**[CHANGE]**

```bash
oc delete pods -A --field-selector=status.phase=Failed
oc delete pods -n openstack --field-selector=status.phase=Succeeded -l app=openstackansibleee
```

If a container is repeatedly `OOMKilled` at its own limit, the limit is too
low for the workload. Service templates accept a `resources` section;
operator pods are tuned through `operatorOverrides` of the `OpenStack`
initialization resource.

If the node is simply too small, give it a bigger flavor in the host cloud
(a resize is a node reboot: see [node and OKD](node-and-okd.md)) or add a
worker node; both are infrastructure changes outside this runbook.

## 6. Verification

**[READ-ONLY]**

```bash
oc adm top node
oc describe node | grep -A6 'Conditions:'
oc get pods -A | grep -v 'Running\|Completed' || true
oc get openstackcontrolplane openstack
```

Watch for ten minutes: restart counts must stop increasing.

## 7. Risks and precautions

- After an eviction or OOM episode, check Galera and RabbitMQ explicitly
  ([runbook](galera-and-rabbitmq.md)); an unclean kill of either has
  consequences beyond the restart.
- Do not remove resource requests to make pods schedulable: it converts a
  clear `Pending` into unpredictable evictions.
- Do not set tight memory limits on Galera or RabbitMQ without measuring;
  an OOM kill of a database is worse than a slow node.
- etcd and the API server share the node. Sustained pressure can make the
  whole cluster unresponsive, at which point `oc` no longer helps and the
  remaining tool is SSH to the node (`ssh core@192.168.130.10` from the
  bastion).
- Disabling a service with a database does not free its data; it frees its
  pods.
