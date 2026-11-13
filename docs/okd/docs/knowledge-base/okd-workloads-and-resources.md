# OKD workloads and resources

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

## In short

- If the node runs out of memory, the OpenStack pods die first: 18 of
  20 have no request (`BestEffort`, `oom_score_adj` 1000), Galera
  included.
- Three numbers describe memory: 72 % requested (what the scheduler
  counts), 62 % used, 11.6 GiB available. `Pending` with
  `Insufficient memory` is a request problem, not a usage problem.
- Requests and limits are set through `resources` in the
  `OpenStackControlPlane`; the pod rolls and the value applies to every
  container of the pod.
- No PodDisruptionBudget, ResourceQuota or LimitRange exists in
  `openstack`. Do not add a LimitRange there.

One node carries the platform, the operators and the OpenStack control
plane. This file records how Kubernetes accounts for CPU and memory on
that node, which pods would be sacrificed first if memory ran out, and
the tools that protect or contain a workload (requests and limits
through the OpenStackControlPlane, quotas, disruption budgets). The
OpenStack-side view of the same subject is in
[Capacity and observability](openstack-capacity-and-observability.md).
Commands run on the bastion as the cluster administrator; `node` stands
for `ssh core@192.168.130.10`.

## Entries

### Which pods die first if the node runs out of memory?

**Context**: memory is the scarce resource of the lab (32 GiB). Before
an incident, know the order of sacrifice; after one, explain why that
pod was killed.

**How**:

**[READ-ONLY]**

```bash
oc get pods -n openstack -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,PRIO:.spec.priority,REQ:.spec.containers[*].resources.requests'
oc get pods -A -o json | python3 -c '
import json, sys, collections
it = [p for p in json.load(sys.stdin)["items"] if p["status"]["phase"] == "Running"]
print(collections.Counter(p["status"]["qosClass"] for p in it))
print(collections.Counter(p["spec"].get("priorityClassName", "-") for p in it))'
# the kernel's view: the higher the score, the earlier the kill
node 'for n in "etcd --logger" mysqld beam.smp "prometheus --config" "kubelet --config"; do p=$(pgrep -o -f "$n"); echo "$n oom_score_adj=$(cat /proc/$p/oom_score_adj)"; done'
# the kubelet's thresholds and the current state
oc get --raw /api/v1/nodes/okd-0/proxy/configz | python3 -c '
import json, sys; k = json.load(sys.stdin)["kubeletconfig"]
print(k["evictionHard"], k.get("evictionSoft"), k["systemReserved"], k["enforceNodeAllocatable"])'
oc get node okd-0 -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
node 'free -m; sudo journalctl -k --since "-20h" | grep -c -i "oom-kill"; grep -E "^oom" /sys/fs/cgroup/kubepods.slice/memory.events'
```

**Observed on the lab** (2026-11-12):

```text
openstack namespace: 18 pods BestEffort (every OpenStack service, both Galera, memcached, OVN databases),
                     2 pods Burstable (the two RabbitMQ: requests 1 CPU / 2Gi, limits 2 CPU / 2Gi)
whole cluster:       111 Burstable, 23 BestEffort, 0 Guaranteed
priority classes:    system-cluster-critical 61 pods, system-node-critical 20, openshift-user-critical 5, none 48
                     (none = priority 0: all of openstack and openstack-operators)
oom_score_adj:       kubelet -999, etcd -997, kube-apiserver -997,
                     rabbitmq (beam.smp) 937, prometheus 969, galera (mysqld) 1000
evictionHard:        memory.available 100Mi, nodefs.available 10%, imagefs.available 15%; no soft eviction
systemReserved:      cpu 500m, memory 1Gi; enforced on pods only
MemoryPressure=False DiskPressure=False PIDPressure=False Ready=True
Mem: total 32086  used 20484  free 2848  buff/cache 9423  available 11601 (MiB); no swap
kernel OOM kills in 20 h: 0
```

The order of sacrifice on this lab is therefore: **the OpenStack
services first** (BestEffort, score 1000: Galera, Keystone, Nova,
Neutron, Glance, OVN databases, all equal — among them the kernel picks
the largest consumer), then monitoring and the Burstable pods with
small requests, RabbitMQ after them, and the platform's static pods
last. With 11.6 GiB available and no kill since installation, this is
theory today; it becomes practice when a service is enabled without
checking the margin.

**Why / how it works**: two mechanisms, in this order of speed.

- The **kernel OOM killer** acts when memory is exhausted. The kubelet
  sets `oom_score_adj` from the QoS class: 1000 for BestEffort (no
  request), `1000 − 1000 × request / node memory` for Burstable (2 GiB
  requested of 32 gives 937), −997 for Guaranteed and critical static
  pods.
- The **kubelet eviction** acts when `memory.available` falls under
  100 MiB: it sets `MemoryPressure`, stops admitting BestEffort pods and
  evicts pods ranked by usage above request, then priority. With a
  threshold this low and no swap, the kernel usually strikes first.

A pod that is killed is restarted by its controller; a pod that is
evicted is recreated when pressure ends (five minutes of transition
period). Priority classes matter for scheduling preemption and eviction
ranking, not for the kernel. Kolla-Ansible equivalent: none of this
exists; all containers are equal before the kernel unless you set
`<service>_dimensions`, and systemd restarts what is killed.

**Pitfalls**:

- Galera has the worst score of the node together with stateless API
  pods. An OOM kill of `mysqld` is a database crash recovery (single
  replica: an outage of all APIs). Giving Galera a memory request is the
  cheapest protection available — see the entry on requests below.
- "BestEffort" does not mean "limited": these pods can take all the
  memory. It means "first to go".
- The 1 GiB system reservation is far below what the host services
  really use (4.4 GiB in `system.slice`, see the node file): the
  scheduler believes it has 30.2 GiB for pods when about 27 exist.
- `MemoryPressure=False` is true until the last 100 MiB. Watch
  `MemAvailable` (monitoring file), not the condition.

**See also**:
[Do the OpenStack pods have requests and limits](openstack-capacity-and-observability.md#do-the-openstack-pods-have-requests-and-limits-and-what-protects-the-node),
[Node and host](okd-node-and-host.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### How do I read the node's requests and limits accounting?

**Context**: "can I enable one more service?"; a pod is `Pending` with
`Insufficient memory` although `free` shows gigabytes.

**How**:

**[READ-ONLY]**

```bash
oc describe node okd-0 | sed -n '/^Capacity:/,/^System Info/p;/^Allocated resources/,/^Events/p'
oc adm top node
# who holds the requests (memory in MiB, CPU in millicores)
oc get pods -A -o json | python3 -c '
import json, sys, collections
def mem(v):
    for s, f in (("Ki", 1/1024), ("Mi", 1), ("Gi", 1024)):
        if v.endswith(s): return float(v[:-2]) * f
    return float(v) / 1048576
def cpu(v): return float(v[:-1]) if v.endswith("m") else float(v) * 1000
m, c = collections.Counter(), collections.Counter()
for p in json.load(sys.stdin)["items"]:
    if p["status"]["phase"] not in ("Running", "Pending"): continue
    for x in p["spec"]["containers"]:
        r = x.get("resources", {}).get("requests", {})
        m[p["metadata"]["namespace"]] += mem(r.get("memory", "0"))
        c[p["metadata"]["namespace"]] += cpu(r.get("cpu", "0"))
for ns, v in m.most_common(8): print(ns.ljust(40), "%6d Mi %5d m" % (v, c[ns]))
print("total".ljust(40), "%6d Mi %5d m" % (sum(m.values()), sum(c.values())))'
```

**Observed on the lab** (2026-11-12):

```text
Capacity:     cpu 16      memory 32856704Ki   pods 250
Allocatable:  cpu 15500m  memory 31705728Ki   pods 250
Allocated resources:
  cpu      requests 4808m (31%)     limits 15010m (96%)
  memory   requests 22431Mi (72%)   limits 16128Mi (52%)
okd-0   1910m   12%   19501Mi   62%                       # oc adm top node: real use

openstack-operators                        6066 Mi   230 m     # real use: 1.4 GiB
openstack                                  4096 Mi  2000 m     # the two RabbitMQ only; real use of the namespace: 3.7 GiB
openshift-ovn-kubernetes                   1950 Mi   100 m
openshift-monitoring                       1895 Mi   147 m     # real use: 3.2 GiB
openshift-kube-apiserver                   1224 Mi   290 m     # real use: 3.3 GiB
openshift-etcd                              960 Mi   370 m
total                                     22431 Mi  4808 m
```

Three different numbers describe "memory": 72 % **requested** (what the
scheduler counts), 62 % **used** (working set), and 11.6 GiB
**available** to the kernel. The scheduler will place new pods until
requests reach 100 % of allocatable: 8.5 GiB of requests are left. The
requests are a poor picture of reality in both directions: the
operators reserve 6 GiB and use 1.4; RabbitMQ reserves 4 GiB and uses
0.33; the 18 OpenStack pods reserve nothing and use 3.4 GiB.

**Why / how it works**: `Allocatable` is capacity minus the system
reservation (1 GiB, 500m) minus the hard eviction threshold (100 MiB).
A request is a promise made at scheduling time: the sum of requests can
never exceed allocatable, whatever the real use. A limit is enforced at
run time by the cgroup (memory: kill; CPU: throttling) and limits may
add up to more than the node ("overcommitted"). A pod with no request
costs the scheduler nothing, which is why the OpenStack control plane
"fits" on paper regardless of what it consumes. Kolla-Ansible
equivalent: no accounting at all; you size the controllers by
experience and watch `free`.

**Pitfalls**:

- The memory percentage of `oc adm top node` is relative to allocatable
  and measures the working set (cache excluded): it reads lower than
  `free`'s "used + cache" and higher than what a naive "free" suggests.
- A `Pending` pod with `Insufficient memory` is a **request** problem,
  not a usage problem: lower a request or remove a workload; freeing
  cache does nothing.
- CPU requests are low (31 %) but CPU limits total 96 %: limits are per
  container and only throttle; the node is CPU-idle (12 %).
- The 6 GiB requested by the operator pods is the largest reservation
  of the cluster, for 1.4 GiB used; see the OLM file for what can be
  done about operators of services that are not deployed.

**See also**: [OLM and operators](okd-olm-and-operators.md),
[How do I query Prometheus](okd-monitoring-and-alerting.md#how-do-i-query-prometheus-from-the-command-line)

### How do I give a control plane service requests and limits, and what does it change?

**Context**: protect a critical service from the OOM killer, or contain
a service that could eat the node. The service administration file did
it for Placement (two containers); this entry repeats it on Keystone
and measures the effect on the host and on availability.

**How**:

**[READ-ONLY]**

```bash
oc get oscp openstack -n openstack -o jsonpath='{.spec.keystone.template.resources}{"\n"}'
oc get pods -n openstack -l service=keystone -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,REQ:.spec.containers[*].resources.requests,LIM:.spec.containers[*].resources.limits'
```

**[CHANGE]** — rolls the Keystone pod.

```bash
oc patch oscp openstack -n openstack --type=merge -p \
  '{"spec":{"keystone":{"template":{"resources":{"requests":{"cpu":"200m","memory":"512Mi"},"limits":{"memory":"1Gi"}}}}}}'
oc rollout status -n openstack deployment/keystone --timeout=120s
oc wait oscp openstack -n openstack --for=condition=Ready --timeout=120s
# effect on the host: cgroup of the pod and score of its processes
POD_UID=$(oc get pod -n openstack -l service=keystone -o jsonpath='{.items[0].metadata.uid}' | tr - _)
node "d=/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod${POD_UID}.slice; cat \$d/memory.max \$d/memory.current \$d/cpu.weight \$d/cpu.max"
```

**[CHANGE]** — revert (rolls the pod again).

```bash
oc patch oscp openstack -n openstack --type=json -p '[{"op":"remove","path":"/spec/keystone/template/resources"}]'
```

**Observed on the lab** (2026-11-12):

```text
before   keystone-<old>   BestEffort   <none>                       <none>
after    keystone-<new>   Burstable    map[cpu:200m memory:512Mi]   map[memory:1Gi]
rollout complete in 34 s, OpenStackControlPlane Ready at 35 s
node accounting   cpu requests 4808m -> 5008m, memory requests 22431Mi -> 22943Mi (74 %), memory limits 16128Mi -> 17152Mi
cgroup            memory.max 1073741824, memory.current 422 MiB, cpu.weight 8 (was 1), cpu.max "max" (no CPU limit)
httpd processes   oom_score_adj 985 (was 1000)
availability      one failed request out of 132 on the public endpoint (probe every 0.5 s) during the roll
revert            35 s; pod BestEffort again, accounting back to 4808m / 22431Mi, spec.keystone.template.resources = {}
```

**Why / how it works**: the OpenStackControlPlane passes `resources` to
the KeystoneAPI resource, whose operator writes it on the container of
the Deployment; the changed pod template triggers a rolling update (new
pod ready before the old one is removed, hence a single failed request
and not an outage). On the host, the request becomes a CPU weight and a
better OOM score; the limit becomes `memory.max` of the pod's cgroup. A
request of 512 MiB of 32 GiB only moves the score from 1000 to 985: to
really protect a service against the BestEffort crowd the request must
be significant, or the others must be worse off — the relative order is
what counts. Kolla-Ansible equivalent: `keystone_dimensions` (for
example `mem_limit`, `cpu_shares`), then `kolla-ansible reconfigure -t
keystone`.

**Pitfalls**:

- Each change of `resources` restarts the service, and the value
  applies to **every** container of the pod: Keystone has one, Placement
  two, Nova API two, Glance two. The reservation is multiplied.
- A memory limit below real use is a crash loop. Keystone used 388 MiB
  right after start and 523 MiB after 16 hours: measure on a pod that
  has run for a while, and leave a wide margin (WSGI workers grow).
- The old ReplicaSet remains (six for Keystone after this morning's
  exercises, `revisionHistoryLimit` default 10): harmless; see the OLM
  file for cleanup.
- The Galera and RabbitMQ templates have the same field
  (`spec.galera.templates.<name>.resources`,
  `spec.rabbitmq.templates.<name>.resources`); changing them restarts
  the database or the message bus — plan it as a maintenance. Not done
  on the lab; listed in the open questions with a proposed sizing.

**See also**:
[How do I give a service CPU and memory requests and limits](openstack-service-administration.md#how-do-i-give-a-service-cpu-and-memory-requests-and-limits),
[Safe change checklist](../operations/09-safe-change-checklist.md)

### What does an out-of-memory kill look like, and how do I find it afterwards?

**Context**: a pod restarted "for no reason"; exit code 137.

**How**:

**[CHANGE]** — a test pod in a scratch namespace, limited to 64 MiB,
that allocates 200 MiB. It uses the image of the `openstackclient` pod,
already present on the node.

```bash
oc create namespace kb-scratch
IMG=$(oc get pod -n openstack openstackclient -o jsonpath='{.spec.containers[0].image}')
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Pod
metadata: {name: oom, namespace: kb-scratch}
spec:
  restartPolicy: Never
  containers:
  - name: c
    image: $IMG
    command: ["python3", "-c", "import time; a = bytearray(200*1024*1024); time.sleep(60)"]
    resources: {limits: {memory: 64Mi}}
EOF
```

**[READ-ONLY]** — the traces, usable for any pod.

```bash
oc get pod -n kb-scratch oom
oc get pod -n kb-scratch oom -o jsonpath='{.status.containerStatuses[0].state.terminated.reason} {.status.containerStatuses[0].state.terminated.exitCode}{"\n"}'
# for a restarted container the same fields are under .lastState.terminated
oc get pods -A -o json | python3 -c '
import json, sys
for p in json.load(sys.stdin)["items"]:
    for c in p["status"].get("containerStatuses", []):
        t = c.get("lastState", {}).get("terminated") or c["state"].get("terminated") or {}
        if t.get("reason") == "OOMKilled": print(p["metadata"]["namespace"], p["metadata"]["name"], c["name"], t.get("finishedAt"))'
node 'sudo journalctl -k --since "-1h" | grep -i -E "oom-kill|Killed process"'
```

**[CHANGE]** — cleanup: `oc delete namespace kb-scratch`.

**Observed on the lab** (2026-11-12):

```text
oom    0/1     OOMKilled   0          5s
OOMKilled 137
kernel: oom-kill:constraint=CONSTRAINT_MEMCG,...,oom_memcg=/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod<uid>.slice,...
kernel: Memory cgroup out of memory: Killed process <pid> (python3) total-vm:215976kB, anon-rss:64732kB, ... oom_score_adj:999
kernel: Tasks in /kubepods.slice/.../crio-<id>.scope are going to be killed due to memory.oom.group set
```

The cluster-wide search for `OOMKilled` returned nothing else: no
platform or OpenStack container has been killed for memory since
installation.

**Why / how it works**: `constraint=CONSTRAINT_MEMCG` says the pod hit
**its own limit**; a node-wide exhaustion reads
`CONSTRAINT_NONE` and the victim is chosen by score (first entry). With
`memory.oom.group` the whole container is killed, not one process. The
kubelet reports reason `OOMKilled`, exit code 137 (128 + SIGKILL) and
restarts the container according to the pod's restart policy.
Kolla-Ansible equivalent: `docker inspect` shows `OOMKilled: true`; the
kernel line is the same.

**Pitfalls**:

- `lastState` keeps only the **last** termination, and disappears with
  the pod. The kernel journal keeps the history (as long as the journal
  does); Prometheus keeps the restart count.
- Exit code 137 without `OOMKilled` is a plain SIGKILL: a failed
  liveness probe or a termination grace period that expired.
- A pod with only a limit gets a request equal to the limit; with a
  LimitRange (entry below) it gets the namespace defaults.

**See also**:
[Pod pending or crash loop](../troubleshooting/pod-pending-or-crashloop.md),
[Monitoring and alerting](okd-monitoring-and-alerting.md)

### Do PodDisruptionBudgets protect the control plane here?

**Context**: before draining the node or deleting pods: will Kubernetes
stop me from taking down the last replica?

**How**:

**[READ-ONLY]**

```bash
oc get pdb -A
oc get sts,deploy -n openstack -o custom-columns='KIND:.kind,NAME:.metadata.name,REPLICAS:.spec.replicas'
```

**[CHANGE]** — demonstration in a scratch namespace: a budget that
requires one pod, and one pod.

```bash
cat <<EOF | oc apply -f -
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: keep-one, namespace: kb-scratch}
spec:
  minAvailable: 1
  selector: {matchLabels: {app: kb}}
EOF
# an eviction (what "oc adm drain" sends) is refused...
echo '{"apiVersion":"policy/v1","kind":"Eviction","metadata":{"name":"plain","namespace":"kb-scratch"}}' \
  | oc create --raw /api/v1/namespaces/kb-scratch/pods/plain/eviction -f -
# ...a delete is not
oc delete pod -n kb-scratch plain
```

**Observed on the lab** (2026-11-12):

```text
openshift-console                         console             maxUnavailable 1   allowed disruptions 1
openshift-console                         downloads           maxUnavailable 1   allowed disruptions 1
openshift-kube-storage-version-migrator   migrator            maxUnavailable 1   allowed disruptions 1
openshift-operator-lifecycle-manager      packageserver-pdb   maxUnavailable 1   allowed disruptions 1
No resources found in openstack namespace.
No resources found in openstack-operators namespace.
15 StatefulSets and 4 Deployments in openstack, all with 1 replica

keep-one   minAvailable 1   allowed disruptions 0
Error from server (TooManyRequests): Cannot evict pod as it would violate the pod's disruption budget.
pod "plain" deleted
```

No budget protects anything OpenStack, and the four platform budgets
allow their single pod to go.

**Why / how it works**: a PodDisruptionBudget only filters
**voluntary evictions** through the eviction API (drain, descheduler,
autoscaler). It does nothing against `oc delete pod`, a rolling update,
a crash or a node failure. With one replica a budget requiring one
available pod would block every drain; nothing in this single-replica
topology has one. Whether the operators create budgets for
multi-replica Galera and RabbitMQ could not be checked here (open
question).
Kolla-Ansible equivalent: none; the operator's discipline ("one
controller at a time") plays this role.

**Pitfalls**:

- On a three-node deployment, a budget with `allowed disruptions 0`
  (one Galera member already down) blocks `oc adm drain` indefinitely:
  that is the protection working, not a bug. Repair the member first.
- On this lab, draining the node evicts everything at once; the node
  file describes the cordon and reboot procedure and why a drain is not
  used.
- `minAvailable: 1` on a single-replica workload makes its node
  undrainable. Do not add budgets "for safety" on a single node.

**See also**: [Node and host](okd-node-and-host.md),
[Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md)

### How do ResourceQuota and LimitRange work, and are any in place?

**Context**: a second team gets a namespace on the cluster (see the
access file) and must not be able to starve the control plane.

**How**:

**[READ-ONLY]**

```bash
oc get resourcequota,limitrange -A
```

**[CHANGE]** — in a scratch namespace.

```bash
cat <<EOF | oc apply -f -
apiVersion: v1
kind: LimitRange
metadata: {name: defaults, namespace: kb-scratch}
spec:
  limits:
  - type: Container
    defaultRequest: {cpu: 50m, memory: 64Mi}
    default: {memory: 128Mi}
    max: {memory: 512Mi}
---
apiVersion: v1
kind: ResourceQuota
metadata: {name: small, namespace: kb-scratch}
spec:
  hard: {pods: "3", requests.memory: 200Mi, limits.memory: 400Mi, persistentvolumeclaims: "0"}
EOF
oc describe resourcequota -n kb-scratch small
oc get events -n kb-scratch --field-selector reason=FailedCreate
```

**Observed on the lab** (2026-11-12):

```text
openshift-host-network   resourcequota/host-network-namespace-quotas   pods: 0/0 ...     # the only one in the cluster

pod created before the LimitRange:   qos=BestEffort resources={}                (unchanged afterwards)
pod created after it, no resources:  qos=Burstable  resources={"limits":{"memory":"128Mi"},"requests":{"cpu":"50m","memory":"64Mi"}}
pod asking for a 1Gi limit:          Forbidden: maximum memory usage per Container is 512Mi, but limit is 1Gi
quota status:                        pods 3/3, requests.memory 128Mi/200Mi, limits.memory 256Mi/400Mi
fourth pod:                          Forbidden: exceeded quota: small, requested: pods=1, used: pods=3, limited: pods=3
Deployment of 2 replicas:            READY 0/2, no error on "oc create"; event FailedCreate "exceeded quota: small ..."
```

No quota and no LimitRange exist in `openstack` or
`openstack-operators`, by design of the operators.

**Why / how it works**: both are admission controls, applied when a pod
is **created**. A LimitRange injects default requests and limits into
containers that have none and rejects values outside its bounds. A
ResourceQuota caps the sums of a namespace (pods, requests, limits,
claims, Services...). Running pods are never modified or removed. Once
a quota covers `requests.memory`, every new pod must have a memory
request, which is why the two objects are used together. Kolla-Ansible
equivalent: none on the control plane; the idea is the same as project
quotas in Nova and Cinder, applied to the platform.

**Pitfalls**:

- A Deployment over quota fails silently: the command succeeds and the
  pods never appear. Look at the events of the namespace or at the
  ReplicaSet's conditions.
- Do **not** put a LimitRange in `openstack`: at their next restart
  every OpenStack pod would receive the default limit, and the first one
  exceeding it would be killed. A ResourceQuota there would block the
  operators' jobs (database sync, bootstrap) just as silently.
- Events of the quota refusals disappear after three hours like all
  events.
- Test pods here ran under the `anyuid` constraint because the
  administrator created them; a normal user's pods get `restricted-v2`
  (access file).

**See also**: [Access and security](okd-access-and-security.md),
[How far back do Kubernetes events go](okd-monitoring-and-alerting.md#how-far-back-do-kubernetes-events-go-and-how-do-i-use-them)
