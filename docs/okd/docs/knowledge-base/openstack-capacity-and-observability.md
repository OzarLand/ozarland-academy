# Capacity and observability

> Status: every command was run on the lab (OKD 4.22, operators 18-stable,
> OpenStack 2023.1 Antelope, one KVM compute node) on 2026-11-12

The lab does not deploy the telemetry operator. Everything below uses
what is already there: the Kubernetes metrics API, the platform
Prometheus of OKD, events and container logs. Commands run on the
bastion; `compute` is the SSH helper defined in
[networking with OVN](openstack-networking-ovn.md).

## Entries

### How much CPU and memory does each OpenStack service use right now?

**Context**: sizing question ("can I add a service?") or a node that
feels slow.

**How**:

**[READ-ONLY]**

```bash
oc adm top node
oc adm top pods -n openstack --sort-by=memory
oc adm top pods -n openstack --containers -l service=neutron
oc adm top pods -n openstack-operators --sort-by=memory
oc adm top pods -A --sort-by=memory | sed -n '1,12p'
for s in $(oc get pods -n openstack -o jsonpath='{range .items[*]}{.metadata.labels.service}{"\n"}{end}' | sort -u | grep .); do
  oc adm top pods -n openstack -l service=$s --no-headers 2>/dev/null |
    awk -v s=$s '{c+=$2; m+=$3} END {printf "%-26s %5dm %6dMi\n", s, c, m}'
done | sort -k3 -n -r
```

**Observed on the lab** (2026-11-12, idle cloud):

```text
okd-0   1958m   12%   18390Mi   59%
neutron                        6m    601Mi
glance                         3m    510Mi
nova-api                       3m    414Mi
keystone                       3m    401Mi
nova-metadata                  2m    258Mi
nova-conductor                 5m    247Mi
placement                     10m    235Mi
openstack-galera              16m    173Mi
```

RabbitMQ used 249 Mi and 0.2 CPU (the busiest pod), the cell broker
153 Mi. The whole `openstack` namespace stayed under 4 Gi. The biggest
consumers of the node are not OpenStack: `kube-apiserver` 3.4 Gi and
`prometheus-k8s` 2.2 Gi. The largest operator pod was
`openstack-operator-controller-manager` (186 Mi).

**Why / how it works**: `oc adm top` reads the metrics API fed by the
kubelet; pods of one service share the label `service=<name>`, which
makes per-service sums easy. Kolla-Ansible equivalent: `docker stats` on
each controller.

**Pitfalls**:

- The RabbitMQ pods have no `service` label, so the per-service loop
  misses them; read them from the plain `top pods` list.
- These figures are for an idle cloud; the Keystone API ran with three
  worker processes per listener. Measure again under load before sizing.
- A completed Job pod has no metrics; "not found" lines in the loop are
  normal.

**See also**: [Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Scale a service](../operations/06-scale-a-service.md),
[Architecture](../architecture.md)

### Do the OpenStack pods have requests and limits, and what protects the node?

**Context**: after an out-of-memory incident somebody asks "which limit
was hit?".

**How**:

**[READ-ONLY]**

```bash
oc get pods -n openstack --field-selector=status.phase=Running \
  -o custom-columns='POD:.metadata.name,QOS:.status.qosClass,REQ:.spec.containers[*].resources.requests,LIM:.spec.containers[*].resources.limits'
oc get pods -n openstack -o jsonpath='{range .items[*]}{.status.qosClass}{"\n"}{end}' | sort | uniq -c
oc describe node okd-0 | sed -n '/Allocated resources/,/Events/p'
oc get limitrange,resourcequota -n openstack
```

**Observed on the lab** (2026-11-12):

```text
     49 BestEffort
      2 Burstable
  cpu                4808m (31%)    15010m (96%)
  memory             22431Mi (72%)  16128Mi (52%)
No resources found in openstack namespace.
```

Only the two RabbitMQ pods declare resources (request 1 CPU and 2 Gi,
limit 2 CPU and 2 Gi). Every other OpenStack container has neither
request nor limit.

**Why / how it works**: the operators leave `resources` empty unless you
set them in the control plane resource, so the pods are `BestEffort`:
the scheduler counts them as zero and, under memory pressure, the kubelet
evicts them **first**. The 72 % of memory "requested" on the node comes
from platform pods, not from OpenStack. Kolla-Ansible equivalent: no
limits by default either (`default_container_dimensions` is empty), but
nothing evicts containers.

**Pitfalls**:

- "No limit" means a leaking service can take the node down; "no request"
  means Galera or OVN databases can be evicted before a less important
  pod with a request.
- The node summary cannot be used for OpenStack capacity planning: add
  the real usage from `oc adm top`.
- Setting resources is a control plane change that rolls the pods; a
  limit that is too low turns into OOM kills. See the entry on requests
  and limits in [service administration](openstack-service-administration.md).

**See also**: [Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Pod pending or CrashLoopBackOff](../troubleshooting/pod-pending-or-crashloop.md)

### Has anything been OOM-killed or restarted?

**Context**: a service answered 503 for a minute during the night.

**How**:

**[READ-ONLY]**

```bash
oc get pods -n openstack --sort-by='.status.containerStatuses[0].restartCount'
oc get pods -A -o json | python3 -c '
import json,sys
rows=[]
for p in json.load(sys.stdin)["items"]:
    for c in p["status"].get("containerStatuses",[]):
        lt=c.get("lastState",{}).get("terminated",{})
        if c["restartCount"]>0:
            rows.append((c["restartCount"], p["metadata"]["namespace"], p["metadata"]["name"], lt.get("reason"), lt.get("finishedAt")))
for r in sorted(rows, reverse=True)[:10]: print(*r)
print("OOMKilled:", [r[2] for r in rows if r[3]=="OOMKilled"])'
oc get events -A --field-selector reason=OOMKilling
oc debug node/okd-0 -q -- chroot /host bash -c 'journalctl -k --since "12 hours ago" | grep -i -c -E "out of memory|oom-kill"'
```

**Observed on the lab** (2026-11-12):

```text
OOMKilled: []
No resources found
0
```

No OOM kill in the cluster and none in the kernel journal of the node for
12 hours. The containers with restarts were platform operators (3 to 7
restarts each since the installation the day before).

**Why / how it works**: a container killed for memory keeps
`lastState.terminated.reason = OOMKilled` until the next restart; the
kernel journal is the second witness when the kill is at node level.
Kolla-Ansible equivalent: `dmesg | grep -i oom` and `docker inspect` on
each host.

**Pitfalls**:

- `lastState` only keeps the **last** termination. Use the Prometheus
  query of the metrics entry below for history.
- `oc debug node` starts a privileged pod and prints a PodSecurity
  warning; it is expected. Do not leave such a pod running.
- An evicted pod (node pressure) is not an OOM kill: look for `Evicted`
  in `oc get pods -A` and in events.

**See also**: [Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Node and OKD](../troubleshooting/node-and-okd.md)

### How do I read events, and how far back do they go?

**Context**: "what happened to this pod an hour ago?"

**How**:

**[READ-ONLY]**

```bash
oc get events -n openstack --sort-by=.lastTimestamp | tail -15
oc get events -n openstack --field-selector type=Warning --sort-by=.lastTimestamp
oc get events -n openstack -o json | python3 -c '
import json,sys,collections
c=collections.Counter((e["type"],e["reason"]) for e in json.load(sys.stdin)["items"])
for k,v in c.most_common(12): print(v,*k)'
oc get events -n openstack --sort-by=.lastTimestamp -o custom-columns=T:.lastTimestamp --no-headers | sed -n 1p
```

**Observed on the lab** (2026-11-12 around 07:15 UTC): the oldest event
kept was from 05:01 UTC, a little over two hours earlier. The only
Warnings were `UnexpectedJob` raised by the backup CronJobs for the Jobs
created by hand.

**Why / how it works**: events are objects with a short lifetime in etcd
(about three hours on OKD). They record scheduling, image pulls, probe
failures, kills and what controllers decide. Kolla-Ansible has no
equivalent; the closest is the Docker daemon journal.

**Pitfalls**:

- After three hours the evidence is gone. For an incident of the previous
  night use Prometheus and the logs instead.
- Events are per namespace: operator problems are in
  `openstack-operators`, node problems in `default`.
- Sort explicitly; the default order is not chronological.

**See also**: [Inspect service status](../operations/01-inspect-service-status.md),
[Pod pending or CrashLoopBackOff](../troubleshooting/pod-pending-or-crashloop.md)

### What metrics can I query without deploying telemetry?

**Context**: you want a history of memory, CPU and restarts per pod, and
the telemetry operator is not installed.

**How**:

**[READ-ONLY]** Query the platform Prometheus from inside its own pod.

```bash
q() { oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- \
        curl -s --data-urlencode "query=$1" http://localhost:9090/api/v1/query; }
q 'sum by (pod) (container_memory_working_set_bytes{namespace="openstack",container!=""})/1024/1024'
q 'max_over_time((sum by (pod) (container_memory_working_set_bytes{namespace="openstack",container!=""}))[6h:5m])/1024/1024'
q 'sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="openstack",container!=""}[5m]))'
q 'increase(kube_pod_container_status_restarts_total{namespace="openstack"}[24h]) > 0'
q 'kube_pod_container_status_last_terminated_reason{namespace="openstack",reason="OOMKilled"}'
q 'kubelet_volume_stats_used_bytes{namespace="openstack"}/1024/1024'
oc get pods -n openshift-user-workload-monitoring
oc get servicemonitor,podmonitor,prometheusrule -n openstack
oc api-resources | grep -i -E 'telemetr|ceilometer|metricstorage'
```

The answer is JSON; pipe it to `python3 -m json.tool` or to a small
formatter.

**Observed on the lab** (2026-11-12): memory per pod matched `oc adm top`
(Neutron 602 Mi, Glance 511 Mi, Nova API 414 Mi). The six-hour maximum
was within 10 % of the current value for every pod. The OOM query
returned nothing. The restart query showed about four restarts for most
OpenStack pods in 24 hours, from the installation-day exercises. The
retention of the platform Prometheus is 15 days. User-workload monitoring
is not enabled, there is no ServiceMonitor in `openstack`, and the
telemetry resource types exist (`telemetries`, `ceilometers`,
`metricstorages`) but nothing is deployed.

**Why / how it works**: the OKD monitoring stack scrapes the kubelet
(cAdvisor) and kube-state-metrics for **all** namespaces, so container
level metrics of OpenStack pods are there from day one. Service-level
metrics (API latency, queue depth) are not. Kolla-Ansible equivalent:
`enable_prometheus: "yes"` deploys cAdvisor, node and service exporters
at once.

**Pitfalls**:

- The session of the lab kubeconfig is certificate-based:
  `oc whoami -t` gives no token, so the usual `curl` against the
  `thanos-querier` Route with a bearer token does not work. The `oc exec`
  form above needs no token.
- `kubelet_volume_stats_used_bytes` reported the same 45 GB for every
  volume: with local volumes on one filesystem the figure is the usage of
  the **whole disk**, not of the claim. The requested size of a claim is
  not enforced either.
- These are infrastructure metrics. An API that answers 500 quickly looks
  perfectly healthy here.

**See also**: [Storage troubleshooting](../troubleshooting/storage.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Enable a service](../operations/05-enable-a-service.md)

### Which exporters already exist in the OpenStack pods?

**Context**: before deploying telemetry, see what RabbitMQ and OVN
already expose.

**How**:

**[READ-ONLY]**

```bash
oc exec rabbitmq-server-0 -c rabbitmq -- bash -c \
  'curl -s http://127.0.0.1:15692/metrics | grep -E "^rabbitmq_(queues|connections|consumers|queue_messages_ready) "'
oc exec rabbitmq-server-0 -c rabbitmq -- bash -c 'curl -s http://127.0.0.1:15692/metrics | grep -c "^rabbitmq_"'
oc exec ovsdbserver-nb-0 -c openstack-network-exporter -- bash -c 'curl -sk https://127.0.0.1:1981/metrics | grep -c "^ovn"'
oc get svc -n openstack | grep 1981
```

**Observed on the lab** (2026-11-12):

```text
rabbitmq_queue_messages_ready 270
rabbitmq_connections 15
rabbitmq_consumers 19
rabbitmq_queues 34
289
14
```

The 270 ready messages are the two notification queues without consumer
(see [service administration](openstack-service-administration.md)). The
Services `ovn-northd-0`, `ovsdbserver-nb-0` and `ovsdbserver-sb-0` expose
port 1981.

**Why / how it works**: RabbitMQ ships its Prometheus plugin (ports 15692
plain and 15691 TLS) and each OVN pod has an
`openstack-network-exporter` sidecar (HTTPS; the 14 series of the
Northbound pod are RAFT cluster state such as `ovn_raft_cluster_leader`).
Nobody scrapes them until the
telemetry operator (or a ServiceMonitor with user-workload monitoring)
is set up. Kolla-Ansible equivalent: `prometheus_rabbitmq_exporter`-style
containers enabled with Prometheus.

**Pitfalls**:

- Reading an exporter by hand gives a snapshot, not a history.
- The OVN exporter answers `Client sent an HTTP request to an HTTPS
  server` to plain HTTP; use `https` and `-k` from inside the pod.
- Enabling user-workload monitoring adds a second Prometheus (memory) on
  a node already at 59 %. It was deliberately not done in this campaign.
- The data plane has a `telemetry` service too (node exporter on the
  compute node); it is not in the NodeSet service list of the lab.

**See also**: [Enable a service](../operations/05-enable-a-service.md),
[Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md)

### Where are the logs and how do I follow one request across services?

**Context**: an instance went to ERROR. With Kolla-Ansible you would grep
the request ID in `/var/log/kolla/*/`.

**How**:

**[READ-ONLY]**

```bash
oc logs nova-api-0 -c nova-api-log --since=90m | grep 'POST /v2.1/servers ' | tail -2
rid=$(oc logs nova-api-0 -c nova-api-log --since=90m | grep 'POST /v2.1/servers ' | grep -o 'req-[0-9a-f-]*' | tail -1)
for p in nova-api-0:nova-api-log nova-scheduler-0:nova-scheduler-scheduler \
         nova-cell0-conductor-0:nova-cell0-conductor-conductor \
         nova-cell1-conductor-0:nova-cell1-conductor-conductor; do
  echo "$p $(oc logs ${p%%:*} -c ${p##*:} --since=90m | grep -c "$rid")"
done
np=$(oc get pod -l service=neutron -o name | sed -n 1p)
oc logs $np -c neutron-api --since=90m | grep -c "$rid"
compute "sudo podman logs --since 90m nova_compute 2>&1 | grep -c '$rid'"
oc logs nova-api-0 -c nova-api-api --since=60m | grep '"POST /v2.1/servers' | tail -2
oc logs -n openstack -l service=nova-conductor --all-containers --prefix --since=10m --tail=2
compute 'sudo journalctl -u edpm_nova_compute --since "15 min ago" --no-pager | tail -2'
```

**Observed on the lab** (2026-11-12), for the boot that failed with
`No valid host` while the compute service was disabled:

```text
nova-api-0:nova-api-log 18
nova-scheduler-0:nova-scheduler-scheduler 13
nova-cell0-conductor-0:nova-cell0-conductor-conductor 25
nova-cell1-conductor-0:nova-cell1-conductor-conductor 0
15
0
<ip> - - [12/Nov/2026:06:53:59 +0000] "POST /v2.1/servers HTTP/1.1" 202 436 "-" "python-novaclient" 2253532μs
```

The request went API, scheduler, cell0 conductor (where the instance was
buried) and never reached cell1 or the compute node. Neutron logged the
same ID as global request ID 15 times.

**Why / how it works**: API pods have two containers: `<name>-log` tails
the service log file (with `nova.api.openstack.requestlog` lines carrying
the request ID) and the main container prints the Apache access log with
the duration in microseconds. Other pods log to standard output. On the
compute node, logs go to `podman logs` and the journal. Nothing keeps
logs after a pod is deleted. Kolla-Ansible equivalent:
`grep -r req-<id> /var/log/kolla/`.

**Pitfalls**:

- The request ID is in the **log** container, the HTTP status and timing
  in the **httpd** container. Check both.
- A failed scheduling ends in the **cell0** conductor. Searching only
  cell1 and the compute node finds nothing.
- `oc logs` only reaches the current and the previous container. After a
  rollout the old pod's logs are gone unless a log collector is in place
  (none on the lab).
- With Nova and Placement in debug by default, 30 minutes of the Nova API
  log were about 1300 lines on an idle cloud and 3100 during the
  exercises; always bound with `--since`. Debug can be turned off per
  service (see [service administration](openstack-service-administration.md)).

**See also**: [Logs](../operations/02-logs.md),
[Data plane troubleshooting](../troubleshooting/dataplane.md),
[compute operations](openstack-compute.md)

### How do I find errors quickly across all pods, and which ones are noise?

**Context**: first look during an incident, or a health review.

**How**:

**[READ-ONLY]**

```bash
for p in $(oc get pods -n openstack --field-selector=status.phase=Running -o name); do
  n=$(oc logs $p --all-containers --since=1h 2>/dev/null | grep -c -E ' ERROR | CRITICAL ')
  [ "$n" != 0 ] && echo "$p $n"
done
oc logs nova-api-0 -c nova-api-log --since=1h | grep ' ERROR ' | cut -c1-200 | tail -3
oc logs -n openstack-operators deploy/nova-operator-controller-manager --since=30m | grep -c .
oc logs -n openstack-operators deploy/keystone-operator-controller-manager --since=30m | grep -i endpoint | tail -2
```

**Observed on the lab** (2026-11-12, one hour that included the
exercises of this knowledge base):

```text
pod/keystone-<id> 976
pod/nova-cell0-conductor-0 31
pod/nova-api-0 13
pod/placement-<id> 6
```

- Keystone: tracebacks `keystone.exception.ServiceNotFound: Could not
  find service: placement`, one per CLI lookup by name. Noise.
- cell0 conductor: the `NoValidHost` of the deliberate failed boot.
- Nova API: `AMQP server on rabbitmq-cell1.openstack.svc:5671 is
  unreachable: [SYS] unknown error (_ssl.c:2501). Trying again in 1
  seconds.` A few times per hour, each followed by a successful
  reconnection; no API call failed.
- The operator logs showed `Reconciled Endpoints successfully` at the time
  the catalog was repaired.

**Why / how it works**: all OpenStack services use the oslo log format
(`<date> <pid> <LEVEL> <module> [req-...]`), so one pattern works for
every pod; operators log one line per reconciliation in their Deployment
in `openstack-operators`. Kolla-Ansible equivalent:
`grep -r ' ERROR ' /var/log/kolla/` or the central logging stack.

**Pitfalls**:

- A Python traceback is one ERROR line **per line of traceback**: 976
  lines in Keystone were a few dozen events.
- An error count without a baseline means little. Record the normal level
  of a quiet hour (here: Nova API below 15, Placement below 10).
- The AMQP reconnection message is recurrent on the lab and comes from
  idle API workers (explained in
  [service administration](openstack-service-administration.md)). Do not
  treat it as the root cause of an unrelated incident.
- The loop took 25 seconds here; narrow it with `-l service=<name>` when
  you know where to look.

**See also**: [Logs](../operations/02-logs.md),
[Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md),
[Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md)

### How much room is left on the compute node?

**Context**: before onboarding a project: how many instances fit?

**How**:

**[READ-ONLY]**

```bash
os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
rp=$(os resource provider list -f value -c uuid | sed -n 1p)
os resource provider inventory list $rp
os resource provider usage show $rp
compute 'nproc; free -m | sed -n 2p; df -h / | sed -n 2p'
compute 'sudo virsh nodeinfo'
compute 'sudo du -sh /var/lib/nova/instances/_base'
```

**Observed on the lab** (2026-11-12):

```text
| VCPU           |              4.0 |        1 |        8 |        0 |         1 |     8 |    0 |
| MEMORY_MB      |              1.0 |        1 |    15729 |      512 |         1 | 15729 |    0 |
| DISK_GB        |              0.9 |        1 |       58 |        1 |         1 |    58 |    0 |
8
Mem:           15729        2107       12885          13        1079       13622
/dev/vda4        59G  7.1G   52G  12% /
```

Schedulable capacity: 32 vCPU, 15217 MB of memory, 51 GB of disk. Memory
is the limit: about 59 instances of the 256 MB flavor, 29 of the 512 MB
one. The host itself used 1.5 GB without any instance and 2.1 GB with
two small instances running.

**Why / how it works**: Placement capacity is
`(total - reserved) * allocation_ratio` per resource class; the
`reserved` values come from `reserved_host_memory_mb` (512) and the disk
reservation for the image cache. Kolla-Ansible equivalent: same commands.

**Pitfalls**:

- 512 MB reserved for a host that uses 1.5 GB when empty is optimistic: with a
  memory ratio of 1.0 the last instances would push the host into swap or
  OOM. Raise `reserved_host_memory_mb` through `nova-extra-config` on a
  real node.
- Project quotas are checked before capacity. The demo project is limited
  to its own quota, far below the node.
- The disk figure is the root filesystem shared with the image cache and
  container images.

**See also**: [compute operations](openstack-compute.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[Data plane changes](../operations/08-dataplane-changes.md)
