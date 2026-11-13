# OKD monitoring and alerting

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

## In short

- The platform monitoring stack runs on defaults: 11 pods, 3.2 GiB of
  memory, 15 days of history in an `emptyDir` that is lost if the
  Prometheus pod is deleted.
- Query it from the bastion with a short-lived token
  (`oc create token prometheus-k8s`) on the `thanos-querier` route.
- Six alerts fire on the healthy lab; only `HighOverallControlPlaneMemory`
  is a real signal. No receiver is configured: nobody is told.
- Nothing knows OpenStack: only container metrics of its pods are
  collected. The RabbitMQ and OVN exporters answer but nobody scrapes
  them.
- Events last three hours: capture them right after an incident.

OKD ships a complete monitoring stack (Prometheus, Alertmanager, node
and Kubernetes exporters) that watches the platform from the first
minute. This file records what runs, what it costs, how to query it
from the command line during an incident, which alerts fire on the lab
and why, and what it does and does not know about OpenStack. For the
OpenStack-side view (capacity, RabbitMQ and Galera checks) see
[Capacity and observability](openstack-capacity-and-observability.md).
Commands run on the bastion as the cluster administrator.

## Entries

### Is the monitoring stack running, and what does it cost?

**Context**: first look, or a memory review of the node (32 GiB shared
with the OpenStack control plane).

**How**:

**[READ-ONLY]**

```bash
oc get co monitoring
oc get pods -n openshift-monitoring
oc adm top pods -n openshift-monitoring --no-headers | sort -k3 -n -r
oc get prometheus -n openshift-monitoring k8s -o jsonpath='retention={.spec.retention} replicas={.spec.replicas} storage={.spec.storage}{"\n"}'
oc get pod -n openshift-monitoring prometheus-k8s-0 -o jsonpath='{.spec.volumes[?(@.name=="prometheus-k8s-db")]}{"\n"}'
oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- du -sh /prometheus
oc get cm -n openshift-monitoring cluster-monitoring-config
oc get pods -n openshift-user-workload-monitoring
oc get route -n openshift-monitoring
```

**Observed on the lab** (2026-11-12):

```text
monitoring   4.22.0-okd-scos.10   True   False   False
alertmanager-main-0              6/6   Running
kube-state-metrics-<hash>        3/3   Running
metrics-server-<hash>            1/1   Running
node-exporter-<hash>             2/2   Running
openshift-state-metrics-<hash>   3/3   Running
prometheus-k8s-0                 6/6   Running
prometheus-operator-<hash>       2/2   Running
thanos-querier-<hash>            6/6   Running
...                                                # 11 pods
prometheus-k8s-0        75m   2354Mi
kube-state-metrics      4m    181Mi
thanos-querier          3m    162Mi
...                                                # total: 0.1 CPU, 3.2 GiB
retention=15d replicas=1 storage=
{"emptyDir":{},"name":"prometheus-k8s-db"}
1.3G    /prometheus                                # after 16 hours
Error from server (NotFound): configmaps "cluster-monitoring-config" not found
No resources found in openshift-user-workload-monitoring namespace.
alertmanager-main   prometheus-k8s   prometheus-k8s-federate   thanos-querier     # routes
```

The stack is complete and healthy, entirely on defaults (no
configuration ConfigMap), with one replica of each component. It is the
third memory consumer of the node (3.2 GiB) after the `openstack`
namespace (3.7 GiB) and the API server (3.3 GiB). Monitoring of user
namespaces is not enabled.

**Why / how it works**: the cluster-monitoring-operator deploys
everything. Prometheus scrapes 66 targets (API server, etcd, kubelet,
node-exporter, every platform operator), keeps 291 000 series in
memory, evaluates 235 alert rules and sends firing alerts to
Alertmanager. `thanos-querier` is the query front end (it also fronts a
second Prometheus if user workload monitoring is enabled);
`metrics-server` serves `oc adm top`. Kolla-Ansible equivalent:
`enable_prometheus` and `enable_grafana` (with the Kolla exporters for
MariaDB, RabbitMQ, memcached, OpenStack) — optional there, built-in
here, but here without anything for OpenStack.

**Pitfalls**:

- The Prometheus database is an `emptyDir` on the node's only disk: it
  survives container restarts and node reboots (the oldest sample on the
  lab predates the night's reboot), but **deleting the pod erases the
  whole history**. Never "fix" Prometheus by deleting its pod during an
  incident you still need to analyse.
- At 1.3 GiB for 16 hours, the 15 days of retention would use roughly
  30 GiB of the 104 GiB free, on the disk shared with etcd and the
  OpenStack volumes. Count it in the disk budget, or cap it with
  `retentionSize` in `cluster-monitoring-config`.
- Prometheus memory grows with the number of series; adding scrape
  targets (user workload monitoring, OpenStack exporters) is paid in
  memory on the same node.
- No Grafana: OKD dropped it. Dashboards are in the web console
  (Observe menu), queries are PromQL.

**See also**: [Node and host](okd-node-and-host.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### How do I query Prometheus from the command line?

**Context**: incident handling without the web console: is memory
falling, is etcd slow, did something restart, is the API returning
errors?

**How**:

**[READ-ONLY]**

```bash
TOKEN=$(oc create token prometheus-k8s -n openshift-monitoring --duration=10m)
H=$(oc get route -n openshift-monitoring thanos-querier -o jsonpath='{.spec.host}')
q() { curl -sk -H "Authorization: Bearer $TOKEN" --data-urlencode "query=$1" "https://$H/api/v1/query" \
  | python3 -c '
import json, sys
for r in json.load(sys.stdin)["data"]["result"]:
    m = r["metric"]; print(" ", ",".join("%s=%s" % (k, m[k]) for k in ("namespace", "pod", "verb", "code", "alertname") if k in m), r["value"][1][:12])'; }

q 'node_memory_MemAvailable_bytes/1024^3'                                   # memory available, GiB
q 'min_over_time(node_memory_MemAvailable_bytes[12h])/1024^3'               # lowest in 12 h
q 'instance:node_cpu_utilisation:rate1m*100'                                # CPU %
q 'topk(8, sum by (namespace) (container_memory_working_set_bytes{container!="",container!="POD"}))/1024^2'
q 'topk(8, sum by (pod) (container_memory_working_set_bytes{namespace="openstack",container!="",container!="POD"}))/1024^2'
q 'sum by (namespace,pod) (increase(kube_pod_container_status_restarts_total[6h])) > 0'   # restarts in 6 h
q 'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])))'
q 'max_over_time(histogram_quantile(0.99, sum by (le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])))[6h:5m])'
q 'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_backend_commit_duration_seconds_bucket[5m])))'
q 'sum(rate(apiserver_request_total{code=~"5.."}[1h]))/sum(rate(apiserver_request_total[1h]))*100'   # API error %
q 'histogram_quantile(0.99, sum by (le,verb) (rate(apiserver_request_duration_seconds_bucket{verb!~"WATCH|CONNECT"}[5m])))'
q 'node_filesystem_avail_bytes{mountpoint="/var"}/1024^3'
q 'etcd_mvcc_db_total_size_in_bytes/1024^2'
q 'up==0'                                                                    # scrape targets down
q 'ALERTS{alertstate="firing"}'

# a value over time: query_range with start, end, step
curl -sk -H "Authorization: Bearer $TOKEN" --data-urlencode 'query=node_memory_MemAvailable_bytes/1024^3' \
  --data-urlencode "start=$(date -u -d '3 hours ago' +%s)" --data-urlencode "end=$(date -u +%s)" \
  --data-urlencode 'step=3600' "https://$H/api/v1/query_range"
```

**Observed on the lab** (2026-11-12, about 12:20 UTC):

```text
memory available            11.1 GiB of 31 (64 % used); lowest in 12 h: 11.06; highest: 20.0 (before the control plane restarted after the night reboot)
CPU                         13 %
memory by namespace (MiB)   openstack 3682, openshift-kube-apiserver 3292, openshift-monitoring 3207,
                            openstack-operators 1426, openshift-ovn-kubernetes 632, openshift-etcd 420
memory by pod, openstack    neutron 622, keystone 524, glance 503, nova-api 359, nova-metadata 261,
                            placement 257, openstack-galera-0 191, rabbitmq-server-0 164
restarts in 6 h             none
etcd WAL fsync p99          8 ms now, 25 ms worst of the last 6 h      (alert thresholds: 500 ms warning, 1 s critical)
etcd backend commit p99     13 ms
API 5xx ratio (1 h)         0 %    (62 requests per second on an idle lab)
API latency p99             GET 22 ms, LIST 78 ms, PATCH 48 ms, POST 24 ms
disk available              103.9 GiB
etcd database size          116 MiB
targets down                none (66 up)
range query                 09:22 11.83, 10:22 11.83, 11:22 11.83, 12:22 11.20 GiB
without token               HTTP 401
```

**Why / how it works**: the `thanos-querier` route exposes the standard
Prometheus HTTP API behind an authenticating proxy that checks the
bearer token against the Kubernetes API. `oc create token` issues a
short-lived token for the `prometheus-k8s` ServiceAccount, which may
query everything; a human needs the `cluster-monitoring-view` role for
the same. A PromQL instant query returns the current value; `[6h]`
windows and `query_range` give history, limited by the 15-day
retention. Kolla-Ansible equivalent: the same API on the Kolla
Prometheus, port 9091, usually without authentication.

**Pitfalls**:

- `kube_pod_container_status_restarts_total` is a counter per
  container that survives node reboots: `ovnkube-node` shows 16, etcd
  10. These are the reboot of the night, not crashes. Always look at
  `increase(...[6h])`, never at the absolute value.
- Metrics of a deleted pod stop; a recreated pod is a new series. "No
  restart" for a Deployment pod can hide that the pod was replaced:
  check the pod's age too.
- `node_memory_MemAvailable_bytes` is the kernel's estimate and
  includes reclaimable cache: it is the right number for "how much is
  left", unlike the `free` column.
- `--data-urlencode` is required: PromQL contains characters the shell
  and the URL both mangle.
- The token lasts 10 minutes here on purpose; do not store long tokens
  in scripts.

**See also**:
[Cluster health and etcd](okd-cluster-health-and-etcd.md),
[Workloads and resources](okd-workloads-and-resources.md)

### Which alerts are firing, and what do they mean?

**Context**: daily check, or the console shows a red bell.

**How**:

**[READ-ONLY]**

```bash
AM=$(oc get route -n openshift-monitoring alertmanager-main -o jsonpath='{.spec.host}')
curl -sk -H "Authorization: Bearer $TOKEN" "https://$AM/api/v2/alerts?active=true" | python3 -c '
import json, sys
for a in json.load(sys.stdin):
    l = a["labels"]; print(l["alertname"], l.get("severity"), l.get("namespace", ""), a["startsAt"][:16])
    print("   ", a["annotations"].get("description", a["annotations"].get("summary", ""))[:200])'
# same, from inside the pod, no token needed
oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- amtool --alertmanager.url=http://localhost:9093 alert query
# the rule behind an alert (expression, duration, severity)
curl -sk -H "Authorization: Bearer $TOKEN" "https://$H/api/v1/rules?type=alert" | python3 -c '
import json, sys
for g in json.load(sys.stdin)["data"]["groups"]:
    for r in g["rules"]:
        if r["name"] == "HighOverallControlPlaneMemory": print(r["labels"], r["duration"], " ".join(r["query"].split()))'
oc get secret -n openshift-monitoring alertmanager-main -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d
```

**Observed on the lab** (2026-11-12): 235 alert rules (35 critical, 175
warning, 24 info), 6 firing, none pending.

| Alert | Severity | Meaning here | Action |
|---|---|---|---|
| `Watchdog` | none | always fires, proves the pipeline works | none; its absence is the problem |
| `AlertmanagerReceiversNotConfigured` | warning | no notification target is configured | expected on a lab; see pitfalls |
| `HighOverallControlPlaneMemory` | warning | control plane node memory use above 60 % for one hour (64 % here) | real signal: the node carries the platform and OpenStack; see the workloads file |
| `InsightsDisabled` | info | remote health reporting is off | expected (no pull secret for it) |
| `SamplesMissingTBRCredential` | warning | the samples operator has no credentials for a vendor registry | harmless; sample image streams are not used |
| `PodSecurityViolation` | info | in the last 24 hours a pod was created that fails the pod security profile its namespace is audited against | expected: `openstack` enforces "privileged" but is audited against a stricter profile, and its pods run with fixed UIDs |

The Alertmanager configuration is the default one: three receivers
(`Default`, `Watchdog`, `Critical`) **with no destination**, grouping by
namespace, repeat every 12 hours, and inhibition of warnings by a
critical alert of the same name and namespace.

**Why / how it works**: Prometheus evaluates each rule; when the
expression is true for the rule's duration the alert moves from
`pending` to `firing` and is sent to Alertmanager, which groups,
inhibits, silences and routes. With empty receivers nothing leaves the
cluster: alerts are visible only to someone who looks (console, or the
commands above). Kolla-Ansible equivalent: `enable_prometheus_alertmanager`
with rules you supply yourself; here the rules come with the platform.

**Pitfalls**:

- Nobody is told. On a platform that matters, configure at least one
  receiver (edit the `alertmanager-main` Secret; e-mail, webhook, chat)
  and route `Watchdog` to a dead man's switch. Not done on the lab,
  which has no outgoing notification channel.
- No rule knows OpenStack: a stopped `nova-compute`, a full RabbitMQ
  queue or a Galera node out of sync fires nothing. Only their symptoms
  at pod level do (`KubePodCrashLooping`, `KubePodNotReady`,
  `KubeStatefulSetReplicasMismatch`).
- `HighOverallControlPlaneMemory` assumes three control plane nodes and
  computes with free + buffers + cache: on a single node it will fire
  permanently above 60 %. Do not silence it for ever; track the real
  margin with `MemAvailable`.
- Several rules have a long duration (`for` one hour for disk filling
  and memory): they tell you late. The queries of the previous entry
  tell you now.

**See also**: [Workloads and resources](okd-workloads-and-resources.md),
[Node and OKD troubleshooting](../troubleshooting/node-and-okd.md)

### How do I silence an alert during a maintenance?

**Context**: a planned operation will trigger known alerts (pod
restarts, node reboot); or one known alert hides the others.

**How**:

**[CHANGE]** — a silence only mutes notifications; it expires by itself.

```bash
am() { oc exec -n openshift-monitoring alertmanager-main-0 -c alertmanager -- amtool --alertmanager.url=http://localhost:9093 "$@"; }
SID=$(am silence add alertname=SamplesMissingTBRCredential --duration=10m --author="$USER" --comment="maintenance test")
am silence query
curl -sk -H "Authorization: Bearer $TOKEN" "https://$AM/api/v2/alerts?silenced=true&active=false"   # state: suppressed
am silence expire "$SID"
# typical maintenance silence: everything of one namespace for one hour
am silence add namespace=openstack --duration=1h --author="$USER" --comment="control plane change <ticket>"
```

**Observed on the lab** (2026-11-12):

```text
ID      Matchers                                 Ends At                  Created By  Comment
<uuid>  alertname="SamplesMissingTBRCredential"  2026-11-12 12:31:36 UTC  kb          maintenance test
 silenced: SamplesMissingTBRCredential suppressed
 still in Prometheus ALERTS: ['firing']
(after expire) no silence left
```

The first form was run and expired; the namespace-wide form is the same
command with another matcher and was not left in place.

**Why / how it works**: a silence is a set of label matchers with an end
time, stored in Alertmanager. Matching alerts keep firing in Prometheus
(the `ALERTS` series, the console's alert list) but are marked
`suppressed` and produce no notification. The web console offers the
same under Observe > Alerting > Silences. Kolla-Ansible equivalent: the
same `amtool` against the Kolla Alertmanager.

**Pitfalls**:

- Silences live in Alertmanager's `emptyDir`: deleting the pod removes
  them (and a muted alert notifies again).
- A broad matcher (`severity=warning`) also mutes what you did not
  foresee. Match on namespace or alert name, and keep the duration
  short; an expired silence is better than a forgotten one.
- Always set `--comment` with the reason: the next operator sees who
  muted what.
- Never silence `Watchdog`.

**See also**:
[Safe change checklist](../operations/09-safe-change-checklist.md)

### How far back do Kubernetes events go, and how do I use them?

**Context**: reconstructing what happened to a pod an hour ago.

**How**:

**[READ-ONLY]**

```bash
oc get events -A --sort-by=.lastTimestamp | tail -20
oc get events -A --field-selector type=Warning --sort-by=.lastTimestamp
oc get events -n openstack --field-selector involvedObject.name=keystone-<hash>
oc get events -A -o json | python3 -c '
import json, sys, collections
it = json.load(sys.stdin)["items"]
ts = sorted(e.get("lastTimestamp") or e.get("eventTime") or "" for e in it)
print("oldest", ts[0][:19], "newest", ts[-1][:19], "count", len(it))
print(collections.Counter(e["reason"] for e in it if e["type"] == "Warning").most_common(8))'
```

**Observed on the lab** (2026-11-12, 12:20 UTC):

```text
oldest 2026-11-12T10:01:00 newest 2026-11-12T12:19:58 count 125
[('FailedScheduling', 4), ('Unhealthy', 1)]
default                    Warning   FailedScheduling   pod/<test pod>          0/1 nodes are available: 1 node(s) were unschedulable.
openshift-authentication   Warning   FailedScheduling   pod/oauth-openshift-...  0/1 nodes are available: 1 node(s) didn't match pod anti-affinity rules.
```

Only the last two to three hours exist. The warnings are the traces of
this morning's exercises: a pod created while the node was cordoned, and
the OAuth pod waiting for its predecessor to terminate (single node,
anti-affinity) — which is the 30-second login outage described in the
access file.

**Why / how it works**: events are ordinary API objects stored in etcd
with a time-to-live of three hours on OKD. They are written by the
kubelet, the scheduler and controllers (including the OpenStack
operators), and are the fastest source for "why is this pod not
running". For anything older, Prometheus has the metrics (15 days), the
journal and pod logs have the text (sizes in the node file), and the
audit log has the API calls (about 10 hours). Kolla-Ansible equivalent:
`docker events` and the journal.

**Pitfalls**:

- An incident that happened during the night has no events left in the
  morning. Capture `oc get events -A -o yaml` during or right after an
  incident, or run `oc adm inspect ns/openstack`, before analysing.
- Events are aggregated: `count` and `lastTimestamp` matter; sorting on
  the creation time misleads.
- `oc describe` shows the events of one object only if they still
  exist: an empty "Events" section means "nothing in three hours", not
  "nothing ever".

**See also**:
[How long are host logs kept](okd-node-and-host.md#how-long-are-host-logs-kept-journal-container-logs-audit),
[Logs](../operations/02-logs.md)

### How do I reach the web console (and other `*.apps` pages) through an SSH tunnel?

**Context**: the cluster's networks are private; only the bastion is
reachable. The console, Alertmanager and the Prometheus UI are web
pages under `*.apps.okd.lab.example.com`.

**How**:

**[READ-ONLY]** — on the workstation. A dynamic (SOCKS) tunnel lets the
bastion resolve the names, so no `/etc/hosts` change is needed.

```bash
ssh -N -D 127.0.0.1:1080 <bastion user>@<bastion address> &
# command line test, names resolved on the bastion side
curl -sk --socks5-hostname 127.0.0.1:1080 -o /dev/null -w '%{http_code}\n' \
  https://console-openshift-console.apps.okd.lab.example.com/
# browser: use a separate profile with SOCKS5 proxy 127.0.0.1:1080 and "proxy DNS through SOCKS", e.g.
chromium --user-data-dir=/tmp/lab-profile --proxy-server="socks5://127.0.0.1:1080"
# then open https://console-openshift-console.apps.okd.lab.example.com
oc get route -n openshift-console; oc get route -n openshift-monitoring
```

**Observed on the lab** (2026-11-12), through the tunnel from the
workstation:

```text
200 https://console-openshift-console.apps.okd.lab.example.com/
200 https://oauth-openshift.apps.okd.lab.example.com/healthz
200 https://keystone-public-openstack.apps.okd.lab.example.com/v3
200 https://api.okd.lab.example.com:6443/version
```

The four HTTP checks were run; the browser step was not (no graphical
session on the workstation used).

**Why / how it works**: the console is a pod behind a route like any
other; logging in redirects the browser to
`oauth-openshift.apps...`, then back. Both names, and the API for `oc`,
must be reachable from the browser, which is why a single-port forward
(`ssh -L 8443:...:443`) fails: the redirect goes to a name the
workstation cannot resolve and the router selects the backend by host
name. The SOCKS tunnel carries any name. The same tunnel serves the
OpenStack public endpoints (Horizon is not deployed on the lab).
Kolla-Ansible equivalent: reaching Horizon or Grafana on the internal
VIP through a jump host.

**Pitfalls**:

- Logging in to the console needs a password identity: `kubeadmin`
  (file `auth/kubeadmin-password` of the installation directory on the
  bastion) or a user of an identity provider; the certificate kubeconfig
  cannot log in to the console.
- The browser will warn about certificates: the console uses the
  cluster ingress CA and the OpenStack routes use `rootca-public`.
  Import the CAs in the dedicated profile rather than clicking through
  on a production platform.
- With `curl`, `--socks5-hostname` (not `--socks5`) is what sends the
  name to the far side.
- The console's Observe menu gives the alert list, silences and a PromQL
  page; it shows nothing OpenStack-specific.

**See also**: [Access and security](okd-access-and-security.md),
[Workstation prerequisites](../installation/README.md)

### What is monitored for OpenStack without the telemetry operator?

**Context**: "is RabbitMQ in Prometheus?" — deciding what must be
checked by hand.

**How**:

**[READ-ONLY]**

```bash
oc get servicemonitor,podmonitor -n openstack; oc get servicemonitor,podmonitor -n openstack-operators
oc get ns openstack openstack-operators -o jsonpath='{range .items[*]}{.metadata.name} cluster-monitoring={.metadata.labels.openshift\.io/cluster-monitoring}{"\n"}{end}'
q 'count by (job) (up{namespace=~"openstack.*"})'
oc get metricstorage,ceilometer -n openstack
oc get svc -n openstack-operators | grep -c metrics
oc get svc -n openstack | grep -E '15691|1981'
# the exporters answer when asked by hand
oc exec -n openstack openstackclient -- sh -c 'curl -sk https://rabbitmq.openstack.svc:15691/metrics \
  | grep -E "^rabbitmq_(queues|connections|queue_messages_ready|alarms_memory_used_watermark) "'
oc exec -n openstack openstackclient -- sh -c 'curl -sk https://ovsdbserver-nb-0.openstack.svc:1981/metrics | grep -v "^#" | cut -d"{" -f1 | cut -d" " -f1 | sort -u | head'
# what the platform does see: containers of the namespace
q 'sum(rate(container_cpu_usage_seconds_total{namespace="openstack",container!=""}[5m]))'
q 'kube_pod_status_ready{namespace="openstack",condition="true"} == 0'
```

**Observed on the lab** (2026-11-12):

```text
No resources found in openstack namespace.              # no ServiceMonitor, no PodMonitor
No resources found in openstack-operators namespace.
openstack cluster-monitoring=                           # namespaces not labelled for platform monitoring
openstack-operators cluster-monitoring=
(0 series)                                              # no scrape target in either namespace
No resources found in openstack namespace.              # MetricStorage/Ceilometer CRDs exist, no instance
21                                                      # operator metrics Services, scraped by nobody
ovn-northd-0  ovsdbserver-nb-0  ovsdbserver-sb-0        # port 1981: openstack-network-exporter sidecars
rabbitmq  rabbitmq-cell1                                # port 15691: RabbitMQ Prometheus plugin
rabbitmq_queue_messages_ready 282
rabbitmq_connections 16
rabbitmq_queues 35
rabbitmq_alarms_memory_used_watermark 0
ovn_raft_cluster_leader  ovn_raft_cluster_log_index_next ...      # 14 series
0.14                                                    # CPU cores used by the openstack namespace
```

What exists, by level:

| Level | Covered by the platform | Missing |
|---|---|---|
| Containers of `openstack` (CPU, memory, restarts, readiness, volumes) | yes: kubelet/cAdvisor and kube-state-metrics see every namespace | — |
| Generic alerts on those pods (crash loop, not ready, PVC filling) | yes | — |
| RabbitMQ, OVN database internals | exporters run and answer on 15691 and 1981 | nobody scrapes them |
| Operators (reconcile counts, errors, queue depth) | metrics Services exist on 8443 | nobody scrapes them |
| Galera, memcached | no exporter | everything |
| OpenStack itself (API latency, agent state, quotas, instances) | nothing | everything: needs the telemetry operator (Ceilometer, MetricStorage) or external probes |
| Compute node (host, libvirt) | nothing: it is not a cluster node | node exporter via the data plane telemetry services |

**Why / how it works**: the platform Prometheus scrapes only namespaces
labelled `openshift.io/cluster-monitoring=true`, through ServiceMonitor
objects. The OpenStack operators create ServiceMonitors only when a
`MetricStorage` resource asks for them, and that path relies on a
second monitoring stack (the Cluster Observability Operator) that this
lab does not install, for memory reasons. The exporters are started
anyway, so a manual `curl` gives an instant reading. Kolla-Ansible
equivalent: `enable_prometheus_openstack_exporter`,
`_rabbitmq_exporter`, `_mysqld_exporter` and so on, each one switch;
here it is one operator plus an additional monitoring stack.

**Pitfalls**:

- "Monitoring is green" says nothing about OpenStack. The checks of
  [Capacity and observability](openstack-capacity-and-observability.md)
  (service lists, agent lists, queue depths, Galera state) remain
  manual and should be scheduled.
- The 282 ready messages are the unconsumed notification queues already
  noted in the open questions (they were growing this morning): visible
  in one `curl`, alerted by nobody.
- Labelling `openstack` with `openshift.io/cluster-monitoring=true` and
  adding ServiceMonitors by hand is technically possible but puts user
  workloads in the platform Prometheus, which the platform reserves for
  itself; the supported route is user workload monitoring
  (`enableUserWorkload: true`, about one more Prometheus of memory) or
  the telemetry operator. Neither was enabled on the lab; listed in the
  open questions.
- The RabbitMQ and OVN exporter endpoints are TLS with the internal CA;
  from outside the cluster they are reachable only on the internalapi
  VIP (RabbitMQ) or not at all (OVN exporters).

**See also**:
[Capacity and observability](openstack-capacity-and-observability.md),
[Enable a service](../operations/05-enable-a-service.md)
