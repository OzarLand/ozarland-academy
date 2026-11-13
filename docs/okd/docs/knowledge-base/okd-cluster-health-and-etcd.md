# OKD cluster health and etcd

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

## In short

- `oc get clusterversion` and `oc get co` are the health dashboard: 34
  operators, all `True False False`. etcd, the API server, the
  scheduler, network, DNS and ingress are the ones OpenStack depends on.
- The control plane is four static pods started by the kubelet; when the
  API is down, look at them with `crictl` on the node.
- etcd has one member, no automatic backup and no defragmentation.
  Take snapshots by hand with `cluster-backup.sh` and copy them off the
  node.
- Platform certificates rotate by themselves while the cluster runs.
  The first-day rotation restarts the API server four times; a cluster
  powered off across an expiry needs manual CSR approval.

OpenStack runs on top of this cluster: when the Kubernetes API, etcd or a
platform operator is unhealthy, every OpenStack operator is blind and
every pod restart is at risk. This file records how the cluster itself is
checked. Commands run on the bastion as the cluster administrator;
`node` is a shell on the OKD node:

```bash
node() { ssh core@192.168.130.10 "$@"; }
```

## Entries

### Which version runs, and is an update in progress or available?

**Context**: first question of any incident ("did something update
itself?") and before planning an upgrade.

**How**:

**[READ-ONLY]**

```bash
oc get clusterversion
oc get clusterversion version -o jsonpath='{.spec.channel}{"\n"}{range .status.history[*]}{.version} {.state} {.startedTime} {.completionTime}{"\n"}{end}'
oc get clusterversion version -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.message}{"\n"}{end}'
oc get clusterversion version -o jsonpath='{.status.capabilities.enabledCapabilities}{"\n"}'
oc adm upgrade
oc get featuregate cluster -o jsonpath='{.spec}{"\n"}'
```

**Observed on the lab** (2026-11-12):

```text
version   4.22.0-okd-scos.10   True   False   15h   Cluster version is 4.22.0-okd-scos.10
stable-scos-4
4.22.0-okd-scos.10 Completed 2026-11-11T19:37:19Z 2026-11-11T20:07:18Z
RetrievedUpdates=True
ReleaseAccepted=True Payload loaded version="4.22.0-okd-scos.10" ...
Available=True Done applying 4.22.0-okd-scos.10
Failing=False
Progressing=False Cluster version is 4.22.0-okd-scos.10
No updates available. You may still upgrade to a specific release image with --to-image ...
{"featureSet":"OKD"}
```

One history line means one installation and no update since. The
installation took 30 minutes from the first operator to `Completed`. All
optional capabilities are enabled (`Build`, `Console`, `ImageRegistry`,
`MachineAPI`, `OperatorLifecycleManager`, ...).

**Why / how it works**: the cluster version operator (CVO) owns one
release image, a list of manifests for every platform operator. It
applies them continuously, so a platform Deployment edited by hand is put
back. `Progressing=True` on this resource means a release is being
rolled out; nothing updates unless `spec.desiredUpdate` is set by an
administrator. Kolla-Ansible equivalent: the `openstack_release` and the
Kolla image tag, except that here the platform is one versioned unit.

**Pitfalls**:

- `Failing=True` with `Available=True` is common during an upgrade and
  names the operator that blocks; read the message, not only the columns.
- "No updates available" depends on the update graph reachable through
  the proxy; an empty answer is not a proof that the release is the
  latest.
- The feature set `OKD` is the default of this distribution, not a
  customisation.

**See also**: [OKD in brief](../concepts/07-okd-in-brief.md),
[OKD upgrade](../lifecycle/07-okd-upgrade.md)

### What are the 34 cluster operators for, and which ones matter to OpenStack?

**Context**: `oc get co` is the health dashboard of the platform; you
need to know which line is an emergency for the cloud and which is not.

**How**:

**[READ-ONLY]**

```bash
oc get co
oc get co --no-headers | awk '$3!="True" || $4!="False" || $5!="False"'
oc get co -o json | python3 -c '
import json,sys
for i in json.load(sys.stdin)["items"]:
    print(i["metadata"]["name"], sorted(set(r.get("namespace","") for r in i["status"].get("relatedObjects",[]) if r.get("namespace"))))'
```

**Observed on the lab** (2026-11-12): 34 operators, all
`Available=True Progressing=False Degraded=False` since the installation;
the second command prints nothing. The third prints the namespaces each
operator manages, which is where its pods and logs are.

Operators the OpenStack control plane depends on directly:

| Operator | Role | Effect on OpenStack when it is down |
| --- | --- | --- |
| `etcd` | Runs and guards the etcd static pod | API read-only or down; nothing reconciles |
| `kube-apiserver` | Kubernetes API static pod and its certificates | `oc` and every operator stop working; running pods keep serving |
| `kube-controller-manager` | Deployments, StatefulSets, Jobs, certificate signing | No pod is recreated, no Job starts (Keystone trust flush, database purge, backups) |
| `kube-scheduler` | Places pods on the node | New pods stay `Pending` |
| `network` | OVN-Kubernetes, Multus, whereabouts | No new pod sandbox, no secondary interface (internalapi, tenant) |
| `dns` | CoreDNS and the node resolver | Services stop resolving `*.svc` names: API calls between services fail |
| `ingress` | The HAProxy router behind every Route | Public OpenStack endpoints (`*.apps`) unreachable |
| `machine-config` | Host operating system, kubelet and CRI-O configuration | No effect until a change is rolled; a change reboots the node |
| `operator-lifecycle-manager`, `-catalog`, `-packageserver`, `marketplace` | Install and update operators from catalogs | Running operators keep working; no install or upgrade |
| `service-ca` | Signs service serving certificates of platform components | Webhooks and metrics of platform pods fail when certificates expire |
| `storage`, `csi-snapshot-controller` | Storage classes and snapshot API | Little here: volumes are static local PersistentVolumes |
| `monitoring` | Prometheus, Alertmanager, node and state metrics | No metrics, no alerts; services unaffected |
| `authentication`, `openshift-apiserver` | OAuth logins and the OpenShift API group (Routes, Projects) | Token logins fail; with `openshift-apiserver` down Routes cannot be read or created |

The others, one line each:

| Operator | Role |
| --- | --- |
| `baremetal` | Bare-metal host management (present, idle: the node is a virtual machine installed by the agent installer) |
| `cloud-controller-manager`, `cloud-credential` | Cloud provider integration; nothing to do on platform `none` |
| `cluster-autoscaler`, `machine-api`, `control-plane-machine-set`, `machine-approver` | Machine life cycle; only the approver matters (it approves kubelet certificate requests) |
| `config-operator` | Maintains the cluster-wide `config.openshift.io` resources |
| `console` | Web console |
| `image-registry` | Internal registry operator (see [storage](okd-storage.md)) |
| `insights` | Remote health reporting; disabled here |
| `kube-storage-version-migrator` | Rewrites stored objects after an API version change |
| `node-tuning` | TuneD profiles on the node |
| `olm` | Operator Lifecycle Manager v1 (`ClusterExtension`); not used by the OpenStack operators |
| `openshift-controller-manager` | Builds, image streams, service account pull secrets |
| `openshift-samples` | Sample image streams and templates |

**Why / how it works**: each platform component is itself managed by an
operator which reports through a `ClusterOperator` resource. The CVO
installs these operators; they install the real workloads. Kolla-Ansible
equivalent: none, the closest is the list of containers
`docker ps` shows on a controller, with a health column added.

**Pitfalls**:

- `insights` reports sub-conditions such as `SCAAvailable=False` and
  `ClusterTransferAvailable=False` on a cluster without a subscription
  token. They are not failures and do not make the operator degraded.
- A `baremetal` or `machine-api` operator that is `Available` does not
  mean the cluster manages machines: there is no Machine object here.
- The count is not fixed: it follows the enabled capabilities. This lab
  has 34 because every capability is enabled.

**See also**: [Node and OKD troubleshooting](../troubleshooting/node-and-okd.md),
[OKD in brief](../concepts/07-okd-in-brief.md)

### How do I read the Degraded and Progressing messages of an operator?

**Context**: one line of `oc get co` is not `True False False`.

**How**:

**[READ-ONLY]**

```bash
oc get co kube-apiserver -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason} {.lastTransitionTime} {.message}{"\n"}{end}'
oc get co etcd -o jsonpath='{range .status.relatedObjects[*]}{.resource}/{.namespace}/{.name}{"\n"}{end}'
oc get kubeapiserver cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason} {.message}{"\n"}{end}'
oc get etcd cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason} {.message}{"\n"}{end}'
oc get kubeapiserver cluster -o jsonpath='{range .status.nodeStatuses[*]}{.nodeName} current={.currentRevision} target={.targetRevision} lastFailed={.lastFailedRevision}{"\n"}{end}'
oc logs -n openshift-etcd-operator deploy/etcd-operator --since=1h | tail -20
```

**Observed on the lab** (2026-11-12):

```text
Degraded=False AsExpected 2026-11-11T19:47:43Z NodeControllerDegraded: All master nodes are ready
Progressing=False AsExpected 2026-11-11T20:01:49Z NodeInstallerProgressing: 1 node is at revision 7
Available=True AsExpected 2026-11-11T19:49:55Z StaticPodsAvailable: 1 nodes are active; 1 node is at revision 7
Upgradeable=True AsExpected 2026-11-11T19:46:48Z KubeletMinorVersionUpgradeable: Kubelet and API server versions are synced.
okd-0 current=7 target=0 lastFailed=0
```

The `etcd` operator resource lists about thirty detailed conditions
(`EtcdMembersAvailable=True EtcdQuorate 1 members are available`,
`NodeInstallerProgressing=False AllNodesAtLatestRevision`,
`DefragControllerDisabled=True`, ...).

**Why / how it works**: the message of a `ClusterOperator` condition is a
concatenation of `<Controller><Type>: text` fragments. The prefix is the
name of the internal controller that complains; the same name appears as
a detailed condition on the operator's own resource
(`kubeapiserver/cluster`, `etcd/cluster`, ...) and in the operator log.
The reading order is therefore: `oc get co` → condition message →
detailed conditions → operator log in the namespace
`openshift-<name>-operator` → workload namespace listed in
`relatedObjects`.

- `Available=False`: the function is down now.
- `Degraded=True`: it works but something is wrong for longer than a
  grace period; it blocks upgrades.
- `Progressing=True`: a new configuration or revision is rolling out. For
  the three control plane operators it means a static pod is about to
  restart.

**Pitfalls**:

- `targetRevision` different from `0` means an installer pod is replacing
  the static pod: on a single node the API disappears for a minute or
  two. Do not start an OpenStack change at that moment.
- A brief `Progressing=True` on `kube-apiserver` after a certificate
  rotation is expected (see the certificate entries below).
- `SINCE` in `oc get co` is the last transition of `Available`, not the
  last time the operator was degraded.

**See also**: [Node and OKD troubleshooting, scenario C](../troubleshooting/node-and-okd.md),
[Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md)

### Where does the control plane itself run, and what are revisions?

**Context**: the API is down and `oc` does not answer; you must find the
control plane from the node.

**How**:

**[READ-ONLY]**

```bash
for ns in openshift-etcd openshift-kube-apiserver openshift-kube-controller-manager openshift-kube-scheduler; do
  oc get pods -n $ns --no-headers
done
oc get pod -n openshift-kube-apiserver kube-apiserver-okd-0 -o jsonpath='{range .spec.containers[*]}{.name} {end}{"\n"}{.metadata.annotations.kubernetes\.io/config\.source}{"\n"}'
node 'sudo ls -la /etc/kubernetes/manifests/ /etc/kubernetes/static-pod-resources/'
node 'sudo crictl ps --name "kube-apiserver|etcd|kube-controller-manager|kube-scheduler"'
```

**Observed on the lab** (2026-11-12):

```text
etcd-okd-0                       5/5   Running     10   15h
installer-2-okd-0                0/1   Completed   0    15h
kube-apiserver-okd-0             5/5   Running     10   15h
installer-7-okd-0                0/1   Completed   0    15h
kube-controller-manager-okd-0    4/4   Running     9    15h
openshift-kube-scheduler-okd-0   3/3   Running     6    15h
kube-apiserver kube-apiserver-cert-syncer kube-apiserver-cert-regeneration-controller kube-apiserver-insecure-readyz kube-apiserver-check-endpoints
file
(crictl also lists the four operators' own containers, in other namespaces)
/etc/kubernetes/manifests/: criometricsproxy.yaml etcd-pod.yaml kube-apiserver-pod.yaml kube-controller-manager-pod.yaml kube-scheduler-pod.yaml
/etc/kubernetes/static-pod-resources/: etcd-certs etcd-pod-2 kube-apiserver-certs kube-apiserver-pod-4 kube-apiserver-pod-7
  kube-apiserver-last-known-good -> .../kube-apiserver-pod-7/kube-apiserver-pod.yaml kube-controller-manager-pod-5 kube-scheduler-pod-6 ...
```

Restart counts (10, 9, 6) are the two node restarts of the lab multiplied
by the number of containers, not crashes. Two `installer-N` pods ended in
`Error` during the installation (controller manager revision 1,
scheduler revision 3); later revisions succeeded and nothing refers to
them.

**Why / how it works**: the four control plane components are static
pods: the kubelet starts them from files in `/etc/kubernetes/manifests`
without asking the API (`config.source: file`). The pod visible through
`oc` is a mirror. Each operator renders a numbered **revision** (pod
manifest, ConfigMaps and Secrets copied under
`static-pod-resources/<name>-pod-<N>`); an `installer-<N>` pod writes it
on the node and the kubelet restarts the component. Certificates are
synchronised into `*-certs` directories by the `cert-syncer` sidecars
without a new revision. Kolla-Ansible equivalent: none; the nearest idea
is the generated `/etc/kolla/<service>/` directory, versioned.

**Pitfalls**:

- When the API is down, only `crictl` on the node shows the truth:
  `oc get pods` shows nothing or stale mirrors (stale for about twenty
  seconds after a restart, see the node reboot runbook).
- Do not edit a file under `/etc/kubernetes/manifests`: the operator
  rewrites it at the next revision. Moving a manifest out of the
  directory stops the component; this is what the restore scripts do.
- Old revision directories are pruned by `revision-pruner` pods; the
  `Completed` installer and pruner pods are history, not garbage to
  delete by hand.

**See also**: [Node and OKD troubleshooting](../troubleshooting/node-and-okd.md),
[OKD node and host](okd-node-and-host.md)

### How do I check etcd: members, health, size, alarms and latency?

**Context**: the API is slow, operators log timeouts or leader election
losses, or you want a baseline before a risky change.

**How**:

**[READ-ONLY]**

```bash
e() { oc exec -n openshift-etcd etcd-okd-0 -c etcdctl -- "$@"; }
e etcdctl member list -w table
e etcdctl endpoint health -w table
e etcdctl endpoint status -w table
e etcdctl alarm list
e sh -c 'etcdctl get / --prefix --keys-only | sed "/^$/d" | cut -d/ -f3 | sort | uniq -c | sort -rn | head'
oc logs -n openshift-etcd etcd-okd-0 -c etcd --since=6h | grep -c 'apply request took too long'
node 'sudo du -sh /var/lib/etcd /var/lib/etcd/member/wal; sudo ls -la /var/lib/etcd/member/snap'
q() { oc exec -n openshift-monitoring prometheus-k8s-0 -c prometheus -- curl -s --data-urlencode "query=$1" http://localhost:9090/api/v1/query; }
q 'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_wal_fsync_duration_seconds_bucket[5m])))'
q 'histogram_quantile(0.99, sum by (le) (rate(etcd_disk_backend_commit_duration_seconds_bucket[5m])))'
q 'etcd_server_leader_changes_seen_total'
```

**Observed on the lab** (2026-11-12, cluster age 16 h):

```text
| <member-id> | started | okd-0 | https://192.168.130.10:2380 | https://192.168.130.10:2379 | false |
| https://192.168.130.10:2379 | true | 11.867284ms | |
| ENDPOINT | VERSION | DB SIZE | IN USE | PERCENTAGE NOT IN USE | QUOTA  | IS LEADER | RAFT TERM |
| ...:2379 | 3.6.13  | 122 MB  | 46 MB  | 63%                   | 8.6 GB | true      | 7         |
(alarm list: empty)
    538 configmaps
    441 serviceaccounts
    440 rolebindings
    386 secrets
    378 clusterroles
483M  /var/lib/etcd
```

5491 keys in total; the OpenStack custom resources are a small part
(45 `dataplane.openstack.org` keys, for example). Latency: WAL fsync p99
7 ms now and 28 ms at worst over 12 hours, backend commit p99 8 ms, one
leader change seen since the last start. The etcd log had 37 "apply
request took too long" warnings in 6 hours, the slowest 798 ms; they
coincide with the five-minute compaction.

**Why / how it works**: the `etcdctl` container of the etcd pod has the
endpoints and client certificates in its environment, so no option is
needed. `DB SIZE` is the file on disk, `IN USE` the live data; the
difference is free pages left by compaction (the API server compacts
every five minutes). The quota (8 GiB by default here) is the size at
which etcd raises a `NOSPACE` alarm and becomes read-only. Raft term 7
counts elections: on one node each start of etcd is an election.
Kolla-Ansible equivalent: none for the control plane (Kolla's etcd, when
deployed, only serves a few services); for importance think of it as the
MariaDB of Kubernetes.

**Pitfalls**:

- The usual upstream guidance is WAL fsync p99 under 10 ms. The lab disk
  goes above it at times and still works because there is a single
  member: no heartbeat can be missed. On three members the same disk
  would cause elections.
- "apply request took too long" (more than 200 ms) is the first sign of
  a slow disk. etcd shares its disk with container images, logs and all
  the OpenStack volumes here (see [storage](okd-storage.md)): a Glance
  upload or a Galera state transfer is visible in etcd latency.
- `etcdctl check perf` writes test keys; it was not run with a load here
  and should not be on a production cluster during the day.
- A single member has no quorum to lose and no redundancy: the etcd
  backup is the only way back.

**See also**: [Backup and restore](../lifecycle/05-backup-and-restore.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[OKD monitoring](okd-monitoring-and-alerting.md)

### Does etcd need defragmentation, and who does it here?

**Context**: `endpoint status` shows most of the file not in use, or an
alert about database size fires.

**How**:

**[READ-ONLY]**

```bash
oc get etcd cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}' | grep -i defrag
oc logs -n openshift-etcd-operator deploy/etcd-operator --since=24h | grep -i defrag | tail
oc get pod -n openshift-etcd etcd-okd-0 -o json | grep -A1 ETCD_QUOTA_BACKEND_BYTES | head -2
q 'etcd_mvcc_db_total_size_in_bytes'
q 'etcd_mvcc_db_total_size_in_use_in_bytes'
```

**Observed on the lab** (2026-11-12):

```text
DefragControllerDisabled=True AsExpected
... Starting #1 worker of DefragController controller ...
"name": "ETCD_QUOTA_BACKEND_BYTES", "value": "8589934592"
122101760   (file)
46587904    (in use)
```

The operator starts its defragmentation controller and then reports it
as **disabled**: no defragmentation ever ran, and the file stayed at
122 MB for a 46 MB content.

**Why / how it works**: on a highly available cluster the etcd operator
defragments one member at a time when fragmentation exceeds a threshold.
Defragmentation blocks the member while it rewrites the file; with a
single member that would be an API outage, so the controller disables
itself on single-node topologies. The free pages are reused by later
writes, so the file does not grow without bound: it stays at its
high-water mark.

**Pitfalls**:

- A manual `etcdctl defrag` exists but stops the only API backend for
  the duration of the rewrite (short at this size). It was not run: at
  1.4 % of the quota there is nothing to gain.
- Watch the ratio between file size and quota, not the fragmentation
  percentage. 63 % "not in use" is normal after an installation, which
  writes and deletes a lot.
- The size that matters for an alert is the file size
  (`etcd_mvcc_db_total_size_in_bytes`) against the quota.

**See also**: [OKD monitoring and alerting](okd-monitoring-and-alerting.md)

### Are there automatic etcd backups, and where is the backup script?

**Context**: before an upgrade or a risky change of the cluster; after
discovering that nobody scheduled a backup.

**How**:

**[READ-ONLY]**

```bash
oc get cronjob,job -A | grep -i -E 'etcd|backup'
oc get crd | grep -i -E 'etcd|backup'
oc get cm -n openshift-etcd etcd-scripts -o jsonpath='{.data}' | python3 -c 'import json,sys; print(list(json.load(sys.stdin).keys()))'
node 'ls -la /usr/local/bin/ | grep -E "cluster-|quorum|disable-etcd"; sudo ls -la /var/lib/etcd-auto-backup /home/core/assets/backup'
```

**Observed on the lab** (2026-11-12):

```text
openstack   cronjob.batch/backup-openstack         @daily ...
openstack   cronjob.batch/backup-openstack-cell1   @daily ...
etcds.operator.openshift.io
galerabackups.mariadb.openstack.org
['cluster-backup.sh', 'cluster-restore.sh', 'disable-etcd.sh', 'etcd-common-tools', 'etcd.env', 'quorum-restore.sh']
-rwxr-xr-x. 1 root root 4759 ... cluster-backup.sh
-rwxr-xr-x. 1 root root 5226 ... cluster-restore.sh
-rwxr-xr-x. 1 root root 1248 ... quorum-restore.sh
/var/lib/etcd-auto-backup: (empty)
```

There is **no automatic etcd backup**: the only scheduled backups are
the two Galera CronJobs created earlier for the databases. The directory
`/var/lib/etcd-auto-backup` exists and is empty, and the API has no
backup schedule resource for etcd on this feature set. The only etcd
snapshot of the lab is the one taken by hand during the lifecycle
validation (`/home/core/assets/backup`, 93 MB, also copied to the
bastion).

**Why / how it works**: the etcd operator ships the scripts on the node.
`cluster-backup.sh <dir>` writes a snapshot plus the static pod
resources; `cluster-restore.sh` rebuilds a single member from them. The
procedure and its measured duration (6 s) are in the backup guide.
Kolla-Ansible equivalent: `kolla-ansible mariadb_backup` is scheduled by
the operator in both worlds; here a second, different backup is needed
for the platform state.

**Pitfalls**:

- An etcd snapshot contains every Secret of the cluster in clear text
  (no encryption at rest is configured). Protect it like a password
  file.
- A snapshot older than the current certificates cannot simply be
  restored after a rotation; take a new one after the first-day rotation
  and after each upgrade.
- The snapshot directory is on the same disk as etcd. Copy it off the
  node.

**See also**: [the etcd restore executed on 2026-11-13](backup-and-restore-drills.md#how-do-i-restore-etcd-on-the-single-node-and-what-really-happens)
(what `cluster-restore.sh` really does on this single member),
[Backup and restore](../lifecycle/05-backup-and-restore.md),
[Rollback limitations](../lifecycle/04-rollback-limitations.md)

### Where are the logs of the API server, controller manager and scheduler, and what is normal in them?

**Context**: an operator reports API errors, a pod is not created, a Job
does not start.

**How**:

**[READ-ONLY]**

```bash
oc logs -n openshift-kube-apiserver kube-apiserver-okd-0 -c kube-apiserver --since=1h | cut -c1 | sort | uniq -c
oc logs -n openshift-kube-apiserver kube-apiserver-okd-0 -c kube-apiserver --since=1h | grep -E '^[EW]' | tail -5
oc logs -n openshift-kube-apiserver kube-apiserver-okd-0 -c kube-apiserver --since=6h | grep 'Trace\[' | tail
oc logs -n openshift-kube-controller-manager kube-controller-manager-okd-0 -c kube-controller-manager --since=1h | tail
oc logs -n openshift-kube-scheduler openshift-kube-scheduler-okd-0 -c kube-scheduler --since=12h | grep -E 'Successfully bound|Unable to schedule' | tail -3
oc get lease -n kube-system kube-controller-manager -o custom-columns=HOLDER:.spec.holderIdentity,RENEW:.spec.renewTime,TRANSITIONS:.spec.leaseTransitions
oc get lease -n openshift-kube-scheduler
oc adm node-logs okd-0 --path=kube-apiserver/
oc adm node-logs okd-0 --path=/
```

**Observed on the lab** (2026-11-12, one hour of API server log):

```text
     26 E
   3625 I
    137 W
E... conn.go:339] Error on socket receive: read tcp 192.168.130.10:6443->192.168.130.5:...: use of closed network connection
W... logging.go:55] [core] ... grpc: addrConn.createTransport failed to connect to {Addr: "192.168.130.10:2379", ...}. Err: connection error: desc = "transport: authentication handshake failed: context canceled"
Trace[...]: ---"Writing http response done" 802ms
"Successfully bound pod to node" pod="openstack/keystone-cron-29908021-..." node="okd-0" evaluatedNodes=1 feasibleNodes=1
HOLDER        RENEW                         TRANSITIONS
okd-0_<uid>   2026-11-12T11:40:01.723623Z   9
```

The controller manager log is all `I` lines; the scheduler writes one
line per pod placed (the hourly Keystone cron pod is the heartbeat of an
idle lab). `oc adm node-logs --path=kube-apiserver/` lists the audit
files, not the container log.

**Why / how it works**: static pods log to standard output like any
container, so `oc logs` works while the API is up; when it is down the
same logs are under `/var/log/pods/openshift-kube-apiserver_*/` on the
node and through `crictl logs`. Log lines start with the severity letter
(`I`, `W`, `E`). The controller manager and the scheduler use a lease
for leader election even with one replica; the number of transitions
counts their restarts.

**Pitfalls**:

- The two warnings shown above are noise on this lab: about 120 per hour
  of "authentication handshake failed: context canceled" towards etcd
  (health probes that close early) and "use of closed network
  connection" from the bastion address (an `oc` client that went away).
  Do not chase them.
- `Trace[` lines are requests slower than 500 ms. A few per hour are
  normal here (56 in 6 hours); a burst points to etcd or to a very large
  LIST.
- The lease `kube-scheduler` in `kube-system` is a stale leftover of the
  bootstrap (no holder, renewed at installation time). The live one is
  in `openshift-kube-scheduler`.

**See also**: [Logs](../operations/02-logs.md),
[OKD access and security](okd-access-and-security.md) for the audit log

### Is the API healthy and fast right now?

**Context**: `oc` feels slow, an operator logs "context deadline
exceeded", or you want to rule the API out quickly.

**How**:

**[READ-ONLY]**

```bash
oc get --raw '/readyz?verbose' | tail -3
oc get --raw '/readyz?verbose' | grep -c '^\[+\]'
oc get --raw /livez
time oc get --raw /api/v1/namespaces/openstack/pods >/dev/null
oc get --raw /metrics | grep '^apiserver_request_total' | sed -E 's/.*code="([0-9]+)".*\} ([0-9.e+]+)$/\1 \2/' | awk '{a[$1]+=$2} END {for (c in a) printf "%s %d\n", c, a[c]}' | sort
oc get --raw /metrics | grep '^apiserver_storage_objects' | sort -t' ' -k2 -n -r | head
q 'histogram_quantile(0.99, sum by (le,verb) (rate(apiserver_request_duration_seconds_bucket{verb!~"WATCH|CONNECT"}[5m])))'
q 'sum by (code) (rate(apiserver_request_total{code=~"5..|429"}[1h]))'
```

**Observed on the lab** (2026-11-12, 11 hours after the last restart):

```text
[+]shutdown ok
readyz check passed
41
ok
real    0m0.124s
200 1290518
201 82424
404 35059
409 6117
429 258
500 75
apiserver_storage_objects{resource="configmaps"} 538
p99 by verb: GET 22 ms, LIST 71 ms, POST 23 ms, PATCH 25 ms, APPLY 67 ms
rate of 5xx and 429 over the last hour: 0
```

41 readiness checks, all passing. The 75 HTTP 500 and 258 HTTP 429
answers are counters since the restart (51 of the 500 are the server's
own `/readyz` while it started); their rate over the last hour is zero.

**Why / how it works**: `/readyz?verbose` lists every internal check
(etcd, informers, post-start hooks). `/metrics` of the API server is
readable by a cluster administrator without Prometheus, which is useful
when monitoring is down; the counters start at zero when the pod starts.
Kolla-Ansible equivalent: `curl` on a service's health check URL and
HAProxy statistics.

**Pitfalls**:

- `/readyz/etcd` as a separate path returned "not found" here; use the
  verbose list and read the `etcd` lines.
- 404 and 409 are normal in volume: controllers probe for objects and
  retry on write conflicts.
- A 429 means the API priority and fairness layer rejected a client. A
  sustained non-zero rate from one client (an operator in a hot loop) is
  worth finding with the `system_client` or `flow_schema` labels.

**See also**: [OKD monitoring and alerting](okd-monitoring-and-alerting.md)

### Which certificates does the platform use, when do they expire and which rotate by themselves?

**Context**: planning a long power-off, a snapshot restore, or answering
"what expires when?" before it becomes an outage.

**How**:

**[READ-ONLY]**

```bash
oc get secrets -A -o json | python3 -c '
import json,sys
r=[]
for i in json.load(sys.stdin)["items"]:
    a=i["metadata"].get("annotations",{})
    if "auth.openshift.io/certificate-not-after" in a:
        r.append((a["auth.openshift.io/certificate-not-after"],i["metadata"]["namespace"],i["metadata"]["name"]))
for x in sorted(r): print(*x)'
node 'sudo ls -la /var/lib/kubelet/pki/; for f in client server; do sudo openssl x509 -in /var/lib/kubelet/pki/kubelet-$f-current.pem -noout -issuer -enddate; done'
echo | openssl s_client -connect api.okd.lab.example.com:6443 2>/dev/null | openssl x509 -noout -subject -issuer -enddate
echo | openssl s_client -connect 192.168.130.10:443 -servername console-openshift-console.apps.okd.lab.example.com 2>/dev/null | openssl x509 -noout -subject -issuer -enddate
oc get secret -n openshift-service-ca signing-key -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -subject -enddate
oc config view --raw -o jsonpath='{.users[0].user.client-certificate-data}' | base64 -d | openssl x509 -noout -subject -issuer -enddate
oc get certificate -n openstack -o custom-columns=NAME:.metadata.name,READY:.status.conditions[0].status,ISSUER:.spec.issuerRef.name,NOTAFTER:.status.notAfter,RENEW:.status.renewalTime
oc get csr
```

**Observed on the lab** (2026-11-12 11:38 UTC, before the first
rotation; installation on 2026-11-11 at 19:25 UTC):

| Certificate | Lifetime seen | Rotated by |
| --- | --- | --- |
| `csr-signer-signer`, `csr-signer` (sign kubelet certificates), `aggregator-client-signer` | **24 hours** at installation (expire 2026-11-12 19:25), longer afterwards (see the next entry) | kube-controller-manager and kube-apiserver operators |
| kubelet client and server certificates (`/var/lib/kubelet/pki`) | until the signer expires (2026-11-12 19:25) | the kubelet, through a CSR approved by the machine approver |
| API server serving certificates (`api.okd...`), control plane client certificates | 30 days (2026-12-11) | kube-apiserver operator |
| `kube-apiserver-to-kubelet-signer`, `kube-control-plane-signer` | 1 year | operator |
| OVN-Kubernetes certificates | 6 months | network operator |
| Ingress wildcard `*.apps.okd.lab.example.com` and its CA | 2 years | ingress operator |
| Service CA | 26 months | service-ca operator |
| etcd signer, peer and serving certificates | 5 years | etcd operator |
| Load balancer, localhost and service network serving signers | 10 years | not rotated |
| `system:admin` client certificate in the installer kubeconfig | 10 years (2036) | **never**; it is in the group `system:masters` |
| OpenStack certificates (37 cert-manager `Certificate` resources) | leaf 5 years, roots 10 years, `nova-metadata-internal-svc` 1 year | cert-manager, at two thirds of the lifetime |

61 Secrets carry the expiry annotation; the nine that expire first are
the 24-hour ones. `oc get csr` returns nothing: the certificate requests
of the installation were already garbage-collected.

**Why / how it works**: the platform is its own certificate authority.
Operators store each certificate in a Secret annotated with
`auth.openshift.io/certificate-not-before` and `-not-after` and
regenerate it before expiry; the kubelet asks for a new certificate
through a `CertificateSigningRequest`. The first signers are deliberately valid
for 24 hours only, so every cluster goes through one rotation during
its first day. Everything is automatic **while the cluster runs**.
OpenStack service certificates are a separate world managed by
cert-manager with four private roots (`rootca-public`,
`rootca-internal`, `rootca-ovn`, `rootca-libvirt`). Kolla-Ansible
equivalent: `kolla-ansible certificates` once, then manual renewal;
here renewal is continuous and the risk is a cluster that was powered
off across an expiry.

**Pitfalls**:

- A cluster that is powered off when the kubelet certificate expires
  comes back with a kubelet that cannot authenticate: pending CSRs must
  be approved by hand (`oc adm certificate approve`), using the
  10-year `system:admin` kubeconfig. Keep that file safe and offline.
- The API certificate is valid 30 days: a lab stopped for more than a
  month needs the recovery procedure, not just a power-on.
- Volume snapshots of the node taken during the first day contain the
  24-hour certificates and cannot be booted as-is afterwards.
- The secret-annotation inventory does not list the kubelet files nor
  the cert-manager certificates; the three sources must be read
  separately.

**See also**: [OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md),
[Where is the TLS certificate authority](openstack-identity-and-tenants.md#where-is-the-tls-certificate-authority-and-how-do-i-export-it),
[OKD access and security](okd-access-and-security.md)

### What happens during the first-day certificate rotation?

**Context**: the day after an installation; or explaining a kube-apiserver
that rolls several times "by itself" around the 24th hour.

**How**:

**[READ-ONLY]**

```bash
oc get secret -n openshift-kube-controller-manager-operator csr-signer-signer csr-signer \
  -o custom-columns='NAME:.metadata.name,FROM:.metadata.annotations.auth\.openshift\.io/certificate-not-before,TO:.metadata.annotations.auth\.openshift\.io/certificate-not-after'
oc get csr
node 'for f in client server; do sudo openssl x509 -in /var/lib/kubelet/pki/kubelet-$f-current.pem -noout -dates; done'
node 'systemctl show kubelet -p NRestarts -p ActiveEnterTimestamp'
oc get pods -n openshift-kube-apiserver -l apiserver -o custom-columns='NAME:.metadata.name,REV:.metadata.labels.revision,START:.status.startTime'
```

**Observed on the lab** (2026-11-12, installation on 2026-11-11 at
19:25 UTC; a script on the bastion ran the commands above every five
minutes from 11:38 UTC):

```text
13:36  kubelet client certificate renewed (CSR approved), still limited
       to the old signer: valid until 19:25
13:43  kube-apiserver revision 8
13:54  kubelet serving certificate renewed, same limit
14:37  csr-signer-signer replaced: valid 60 days (until 2027-01-11)
14:39  kube-apiserver revision 9
14:42  csr-signer replaced: valid 30 days (until 2026-12-12)
14:44  kube-apiserver revision 10
17:53  kubelet client certificate renewed again, now valid until 2026-12-12
17:59  kubelet serving certificate renewed again, same date
18:02  kube-apiserver revision 11
```

The signers were replaced 19 hours 12 minutes after their creation, at
80 % of their 24 hours, not at the expiry time. The kubelet was never
restarted (`NRestarts=0`) and the kube-controller-manager kept its
revision. Every CSR was approved without intervention. Each new
kube-apiserver revision is a restart of the only API server: `oc`
answered "connection refused" for about a minute at 13:42 and briefly
at 18:01 (the two other revisions were not watched from a terminal).
The resize and migrations between compute nodes running at 18:01 were
not affected, and the functional smoke test passed at 18:34. Besides
this rotation, the node asked for 24-hour client certificates for Multus
and OVN-Kubernetes during the afternoon; these come back every day.

**Why / how it works**: the kube-controller-manager operator renews a
signer at 80 % of its life; the new signer goes into the trust bundles
of the API server, which is a new static pod revision each time. The
kubelet renews its own certificates when they approach their end, and a
certificate cannot outlive its signer: the first renewal was cut at the
old signer's expiry and a second one followed once the new signer was
in use. After the first day the lifetimes are 30 and 60 days. Kolla-Ansible
equivalent: none; certificates there do not rotate by themselves.

**Pitfalls**:

- Four kube-apiserver restarts, each an API interruption of up to a
  minute, between the 18th and the 23rd hour after installation: do not
  run an installation step, an update or a long `oc wait` across them
  without a retry.
- A cluster powered off during that window misses the rotation and comes
  back with expired kubelet certificates (see the previous entry).
- A snapshot taken before the 23rd hour holds certificates that are only
  valid until the 24th.

**See also**: [OKD maintenance impact](../lifecycle/06-okd-maintenance-impact.md),
[Where does the control plane itself run, and what are revisions?](#where-does-the-control-plane-itself-run-and-what-are-revisions)
