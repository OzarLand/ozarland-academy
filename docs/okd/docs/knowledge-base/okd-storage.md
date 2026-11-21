---
title: "OKD storage"
description: "OKD storage"
---

# OKD storage

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

## In short

- Storage is twelve static 10Gi local volumes, directories of the node
  under `/var/lib/openstack-lab-pv`. No provisioner: when they are used
  up, claims stay `Pending`.
- The 10Gi is a label, not a limit. All OpenStack data is 1.2 GiB, on
  the same 150 GiB disk as etcd, images and logs.
- Deleting a claim never deletes data (`Retain`): the volume becomes
  `Released` and must be erased and detached by hand before reuse.
- A recreated claim takes a new, empty volume. For Galera that means
  empty databases: look at `oc get pv` before and after.
- There is no internal image registry: every image comes from external
  registries through the proxy.

The lab has no storage system: the persistent data of the OpenStack
control plane (Galera, RabbitMQ, OVN databases, Glance images) lives in
plain directories of the node's single disk, published to Kubernetes as
static local PersistentVolumes. The same disk carries etcd, the
container images and all logs. This file records how claims bind, where
the data really is and how big, what happens when a claim is deleted,
how to watch the shared disk, and what the removed image registry
implies. Fault scenarios are in
[Storage troubleshooting](../troubleshooting/storage.md). Commands run
on the bastion as the cluster administrator; `node` stands for
`ssh core@192.168.130.10`.

## Entries

### How is persistent storage provided, and how does a claim find its volume?

**Context**: a new service asks for a volume; a claim stays `Pending`;
you wonder which of the twelve volumes a claim will get.

**How**:

**[READ-ONLY]**

```bash
oc get sc -o custom-columns='NAME:.metadata.name,PROV:.provisioner,BIND:.volumeBindingMode,RECLAIM:.reclaimPolicy'
oc get pv -o custom-columns='NAME:.metadata.name,CAP:.spec.capacity.storage,RECLAIM:.spec.persistentVolumeReclaimPolicy,STATUS:.status.phase,CLAIM:.spec.claimRef.name,PATH:.spec.local.path'
oc get pvc -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase,VOLUME:.spec.volumeName,REQ:.spec.resources.requests.storage,CAP:.status.capacity.storage'
oc get pvc -n openstack -o custom-columns='NAME:.metadata.name,OWNER:.metadata.ownerReferences[*].kind'
oc get sts -n openstack -o custom-columns='NAME:.metadata.name,RETAIN:.spec.persistentVolumeClaimRetentionPolicy'
oc get pv local-storage-01 -o yaml
oc get co storage -o jsonpath='{.status.conditions[?(@.type=="Available")].message}{"\n"}'
```

**[CHANGE]** — demonstration in a scratch namespace: one claim that
fits, one that cannot.

```bash
oc create namespace kb-scratch
cat <<EOF | oc apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata: {name: data, namespace: kb-scratch}
spec:
  storageClassName: local-storage
  accessModes: [ReadWriteOnce]
  resources: {requests: {storage: 1Gi}}
EOF
oc get pvc -n kb-scratch; oc describe pvc -n kb-scratch data | sed -n '/Events/,$p'
# then a pod that mounts the claim (any image present on the node), and again: oc get pvc -n kb-scratch
```

**Observed on the lab** (2026-11-12):

```text
local-storage   kubernetes.io/no-provisioner   WaitForFirstConsumer   Delete
local-storage-01 .. local-storage-12: 10Gi each, Retain, path /var/lib/openstack-lab-pv/pv01 .. pv12
9 Bound, 3 Available (04, 08, 09)
openstack   glance-glance-default-single-0             Bound   local-storage-01   10Gi   10Gi
openstack   mysql-db-openstack-galera-0                Bound   local-storage-10   5Gi    10Gi
openstack   mysql-db-openstack-cell1-galera-0          Bound   local-storage-07   5Gi    10Gi
openstack   mysql-backup-openstack                     Bound   local-storage-11   5Gi    10Gi
openstack   mysql-backup-openstack-cell1               Bound   local-storage-02   5Gi    10Gi
openstack   ovndbcluster-nb-etc-ovn-ovsdbserver-nb-0   Bound   local-storage-12   5Gi    10Gi
openstack   ovndbcluster-sb-etc-ovn-ovsdbserver-sb-0   Bound   local-storage-05   5Gi    10Gi
openstack   persistence-rabbitmq-server-0              Bound   local-storage-03   10Gi   10Gi
openstack   persistence-rabbitmq-cell1-server-0        Bound   local-storage-06   10Gi   10Gi
storage operator: "No default StorageClass for this platform"

scratch claim of 1Gi, no pod yet:  Pending, event "waiting for first consumer to be created before binding"
after a pod mounts it:             Bound to local-storage-04, capacity 10Gi
scratch claim of 20Gi with a pod:  Pending; pod event "0/1 nodes are available: 1 node(s) didn't find available persistent volumes to bind"
```

Seven claims belong to the control plane; the two `mysql-backup-*`
claims come from the GaleraBackup resources added by the backup
exercise of the lifecycle guide. Three volumes are free.

**Why / how it works**: the installation script creates twelve
directories on the node and twelve PersistentVolume objects of type
`local`, each with a node affinity for `okd-0`. The class has **no
provisioner**: nothing creates volumes on demand. A claim binds to one
whole volume with the same class, enough capacity and compatible access
modes; which of the eligible volumes is chosen is not predictable (the
mapping above is scattered). `WaitForFirstConsumer` delays the binding
until a pod uses the claim, so that the scheduler can pick a volume on
the node where the pod will run; a claim without a pod stays `Pending`
and that is normal. A claim gets the volume's capacity (10Gi), whatever
it asked for. Kolla-Ansible equivalent: named Docker volumes under
`/var/lib/docker/volumes` (`mariadb`, `rabbitmq`, `glance`), created
implicitly; here they are explicit objects with a life cycle.

**Pitfalls**:

- `RECLAIM Delete` on the class is misleading: it applies only to
  dynamically provisioned volumes. The volumes themselves say `Retain`,
  which is what counts (see the entry on deleted claims).
- There is no default class: a claim without `storageClassName` stays
  `Pending` for ever with no helpful event. The control plane resource
  sets it once (`spec.storageClass: local-storage`).
- Three free volumes means three more claims, no more. Enabling a
  service that needs storage (Cinder with a file backend, Swift,
  telemetry) or a second backup can exhaust them; raise
  `STORAGE_PV_COUNT` and re-run the platform step first.
- Local volumes pin the pod to the node. On one node this is invisible;
  on three, a Galera member can never move to another node with its
  data.

**See also**: [Storage troubleshooting](../troubleshooting/storage.md),
[Platform services](../installation/03-platform-services.md),
[Configuration, secrets and data](../concepts/04-configuration-secrets-and-data.md)

### Where is each claim's data on the node, and how big is it really?

**Context**: before a backup, when the disk fills, or to check what a
service really stores.

**How**:

**[READ-ONLY]**

```bash
# claim -> volume -> directory
oc get pv -o custom-columns='PATH:.spec.local.path,CLAIM:.spec.claimRef.name' --sort-by=.spec.local.path
node 'sudo du -sh /var/lib/openstack-lab-pv/*; sudo ls -ldZ /var/lib/openstack-lab-pv/pv01 /var/lib/openstack-lab-pv/pv10'
node 'for p in pv01 pv03 pv05 pv10 pv11; do echo "$p: $(sudo ls /var/lib/openstack-lab-pv/$p | head -4 | tr "\n" " ")"; done'
# what the pod sees
oc exec -n openstack openstack-galera-0 -c galera -- df -h /var/lib/mysql
# what Kubernetes reports per claim
oc get --raw /api/v1/nodes/okd-0/proxy/stats/summary | python3 -c '
import json, sys
for p in json.load(sys.stdin)["pods"]:
    for v in p.get("volume", []):
        if "pvcRef" in v: print(v["pvcRef"]["name"], "used %d MiB of %d GiB" % (v["usedBytes"] / 2**20, v["capacityBytes"] / 2**30))'
```

**Observed on the lab** (2026-11-12):

```text
pv01  glance-glance-default-single-0              22M   images  os_glance_staging_store  os_glance_tasks_store
pv02  mysql-backup-openstack-cell1               186M
pv03  persistence-rabbitmq-server-0              3.0M   rabbit@rabbitmq-server-0.rabbitmq-nodes.openstack ...
pv05  ovndbcluster-sb-etc-ovn-ovsdbserver-sb-0   1.4M   ovnsb_db.db ...
pv06  persistence-rabbitmq-cell1-server-0         57M
pv07  mysql-db-openstack-cell1-galera-0          326M
pv10  mysql-db-openstack-galera-0                374M   mysql
pv11  mysql-backup-openstack                     235M   data  transfer
pv12  ovndbcluster-nb-etc-ovn-ovsdbserver-nb-0   368K
pv04, pv08, pv09 (Available)                        0
total: 1.2 GiB for "90 GiB" of bound volumes

drwxrwsrwx. 42415 42415 system_u:object_r:container_file_t:s0:c287,c859 /var/lib/openstack-lab-pv/pv01
in the Galera pod:    /dev/vda4  150G  46G  104G  31% /var/lib/mysql
kubelet, every claim: used 46 7xx MiB of 149 GiB
```

**Why / how it works**: a `local` volume is a bind mount of the
directory into the pod. There is no block device, no file system and no
quota behind the "10Gi": the pod sees the node's whole 150 GiB file
system. The kubelet reports per-volume statistics by calling `statfs`,
so every claim shows the usage of the entire disk. The directories are
world-writable with the set-group-ID bit so that pods running as
different service users (42415 for Glance) can write; the SELinux label
is set by the container runtime at mount time. Kolla-Ansible
equivalent: `du -sh /var/lib/docker/volumes/*`.

**Pitfalls**:

- **The 10Gi is not a limit.** A test pod wrote 1.2 GiB in a claim of
  1Gi without any error; it could have written 104 GiB. Glance images,
  a runaway Galera binary log or a RabbitMQ backlog can fill the disk
  that etcd lives on. Nothing but monitoring of the disk stops it.
- The platform alerts on claims (`KubePersistentVolumeFillingUp`) do
  not help: their expressions only cover the `openshift-*`, `kube-*`
  and `default` namespaces, so no claim of `openstack` is ever alerted;
  and the kubelet figures they use follow the whole disk anyway
  (`kubelet_volume_stats_used_bytes` reads 45 GiB for every claim). Use
  `du` on the directories and the node file system alerts.
- The directory names say nothing (`pv07`); always go through
  `oc get pv` to find which service is where — the mapping differs on
  every installation.
- A file-level copy of a Galera directory while `mysqld` runs is not a
  backup; use the GaleraBackup resources or a dump (backup guide).

**See also**: [Backup and restore](../lifecycle/05-backup-and-restore.md),
[Node and host](okd-node-and-host.md)

### What happens to the data when a claim is deleted, and how do I reuse the volume?

**Context**: a service was disabled and re-enabled, a StatefulSet's
claim was deleted to "start clean", or `oc get pv` shows `Released`.

**How**:

**[CHANGE]** — scratch namespace: write in a claim, delete pod and
claim, look at the volume.

```bash
oc exec -n kb-scratch user -- sh -c 'echo hello > /data/proof'
oc delete pod -n kb-scratch user; oc delete pvc -n kb-scratch data
oc get pv -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,CLAIM:.spec.claimRef.name,NS:.spec.claimRef.namespace'
node 'sudo ls -la /var/lib/openstack-lab-pv/pv04'
```

**[DESTRUCTIVE]** — recycle a `Released` volume: erase its content,
then detach it from the vanished claim. Check twice which directory you
empty.

```bash
PV=local-storage-04
P=$(oc get pv $PV -o jsonpath='{.spec.local.path}'); echo "$P"
oc get pv $PV -o jsonpath='{.status.phase} {.spec.claimRef.namespace}/{.spec.claimRef.name}{"\n"}'   # must be Released
node "sudo find $P -mindepth 1 -delete"
oc patch pv $PV --type=json -p '[{"op":"remove","path":"/spec/claimRef"}]'
oc get pv $PV
```

**Observed on the lab** (2026-11-12):

```text
after deleting the claim:  local-storage-04   Released   data   kb-scratch
on the node:               proof (6 bytes) and big (1.2G) still present in pv04
same claim created again:  bound to local-storage-08, empty directory — not to the old volume
after the recycle:         local-storage-04 Available, directory empty
final state:               9 Bound, 3 Available, as before the exercise
```

**Why / how it works**: with reclaim policy `Retain`, deleting a claim
never deletes data. The volume keeps a reference to the dead claim
(`claimRef` with its unique identifier) and enters `Released`: it is
not offered to any other claim, not even one with the same name, since
the identifier differs. An administrator decides: recover the data,
then erase and remove `claimRef` to make the volume `Available` again.
Removing `claimRef` **without** erasing hands the old data to the next
claim, which is exactly how to give a database directory back to a
recreated service (the next claim that binds gets it, so make sure
only one claim is waiting). Kolla-Ansible equivalent: `docker volume
rm mariadb` is the explicit deletion; without it the volume and its
data wait for the next container.

**Pitfalls**:

- Nothing deletes a claim automatically here: the nine claims have no
  owner reference and the StatefulSets keep their claims when scaled
  down or deleted (`persistentVolumeClaimRetentionPolicy` is `Retain`
  for both). Data is orphaned only when somebody deletes a claim by
  hand — typically to "reset" a service. The recreated claim then
  takes a **new, empty** volume while the old data sits in a `Released`
  one: for Galera, empty databases. Look at `oc get pv` before and
  after any operation that deletes claims.
- The reverse also holds: deleting a service resource leaves its claim
  and data behind, still `Bound` and still counted in the pool.
- Each `Released` volume is one volume less in the pool of twelve; with
  three free, the fourth claim stays `Pending`.
- The erase command is a recursive delete as root on the node. Print
  the path first; an empty variable must never reach `find`.

**See also**:
[Storage troubleshooting, scenario B](../troubleshooting/storage.md),
[Rollback limitations](../lifecycle/04-rollback-limitations.md)

### etcd, images, logs and volumes share one disk: what are the risks and how do I watch it?

**Context**: capacity review; alert on disk space; etcd reported slow.

**How**:

**[READ-ONLY]**

```bash
node 'lsblk -o NAME,SIZE,TYPE /dev/vda; df -h /var | tail -1; df -i /var | tail -1'
node 'sudo du -sh /var/lib/etcd/member/snap/db /var/lib/etcd/member/wal /var/lib/containers/storage/overlay \
  /var/lib/kubelet/pods /var/log /var/lib/openstack-lab-pv'
node 'sudo podman system df'
oc get --raw /api/v1/nodes/okd-0/proxy/configz | python3 -c '
import json, sys; k = json.load(sys.stdin)["kubeletconfig"]
print(k["evictionHard"], k["imageGCHighThresholdPercent"], k["imageGCLowThresholdPercent"], k["containerLogMaxSize"], k["containerLogMaxFiles"])'
# the biggest writers in pods' ephemeral storage
oc get --raw /api/v1/nodes/okd-0/proxy/stats/summary | python3 -c '
import json, sys
s = json.load(sys.stdin)
for u, n in sorted(((p.get("ephemeral-storage", {}).get("usedBytes", 0), p["podRef"]["namespace"] + "/" + p["podRef"]["name"]) for p in s["pods"]), reverse=True)[:5]:
    print("%6d MiB %s" % (u / 2**20, n))'
# etcd's view of the disk: see the Prometheus queries of the monitoring file (WAL fsync p99, backend commit p99)
```

**Observed on the lab** (2026-11-12):

```text
vda4 149.5G, one XFS file system mounted on /var: 46G used, 104G available (31 %), inodes 1 %
etcd database 117M, etcd WAL 367M
container images and layers 31G   (153 images, 9.9 GB reclaimable: old operator and release images)
pod volumes and emptyDirs 5.5G    (console "downloads" pod 3.2G, Prometheus 1.3G)
logs 2.9G
OpenStack volumes 1.2G
kubelet: evict pods under 10 % free (nodefs) or 15 % (imagefs); image garbage collection starts at 85 % used, down to 80 %;
         container logs 50Mi x 5 files
etcd WAL fsync p99 8 ms now, 25 ms worst in 6 h; backend commit p99 13 ms
```

**Why / how it works**: a CoreOS host has a single data partition;
`/var/lib/etcd`, `/var/lib/containers`, `/var/lib/kubelet`, `/var/log`
and the lab's volume directories are folders of it. Two distinct risks
follow.

- **Space**: whoever fills the disk fills it for everybody. At 85 % the
  kubelet deletes unused images; between 15 and 10 % free it sets
  `DiskPressure` and evicts pods (the OpenStack pods first, as
  BestEffort); at 100 % etcd cannot write and the API stops. The platform alerts
  (`NodeFilesystemSpaceFillingUp`) fire under 15 % free **and** a
  predicted exhaustion.
- **Latency**: etcd needs each write flushed to disk within
  milliseconds; any heavy writer on the same disk (image pulls, a
  Glance upload, a database dump, a log storm) delays it. Sustained
  fsync p99 above 100 ms gives leader-election warnings and slow API
  calls; the alerts are at 500 ms and 1 s.

Kolla-Ansible equivalent: the controllers' `/var/lib/docker` holding
MariaDB, RabbitMQ and images together — the same space risk, without
the etcd latency sensitivity.

**Pitfalls**:

- The lab's margin is comfortable (104 GiB) but the growth is not
  bounded: 15 days of Prometheus (about 30 GiB at the current rate),
  Glance images (no limit, see above), audit and journal (capped, node
  file). Recompute before uploading large images: Glance's store is this
  disk.
- `podman system df` and `crictl images` show what garbage collection
  could reclaim; do not prune by hand on a healthy node — the kubelet
  does it at the threshold, and a manual prune removes images the next
  pod restart must pull again (from the Internet, through the proxy).
- A dump or a large copy on this disk during production hours is felt by
  etcd. Watch the fsync query while doing it, and throttle (`ionice`,
  `pv -L`) if it climbs.
- `du` on `/var/lib/containers/storage` without excluding the overlay
  mounts counts layers several times (138G reported on a 46G disk). Use
  `df` for the truth and `du` only on leaf directories.

**See also**:
[Cluster health and etcd](okd-cluster-health-and-etcd.md),
[How do I query Prometheus](okd-monitoring-and-alerting.md#how-do-i-query-prometheus-from-the-command-line),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### The image registry is "Removed": what does that imply?

**Context**: `oc get co image-registry` says "The registry is removed";
a build, an `oc new-app` or a tutorial expects an internal registry.

**How**:

**[READ-ONLY]**

```bash
oc get configs.imageregistry.operator.openshift.io cluster -o jsonpath='{.spec.managementState} {.spec.storage}{"\n"}'
oc get co image-registry -o jsonpath='{.status.conditions[?(@.type=="Available")].message}{"\n"}'
oc get pods,cronjob -n openshift-image-registry
oc get imagestream -A --no-headers | wc -l
oc get bc,builds -A
```

**Observed on the lab** (2026-11-12):

```text
Removed {}
Available: The registry is removed / NodeCADaemonAvailable ... / ImagePrunerAvailable: Pruner CronJob has been created
cluster-image-registry-operator   1/1 Running
node-ca-<id>                      1/1 Running
image-pruner-<id>                 0/1 Completed      (CronJob "0 0 * * *")
36 image streams, no BuildConfig, no Build
```

The operator runs, the registry itself does not exist: no registry pod,
no `image-registry` Service, no storage.

**Why / how it works**: on platforms without shared storage the
installer sets the registry to `Removed` rather than guess a backend.
Nothing in the lab needs it: every image (platform, operators,
OpenStack services) is pulled by the node from external registries
through the proxy, and cached in `/var/lib/containers`. Consequences:

- **Works without it**: all deployments here; `oc adm must-gather` (it
  pulls its image from an external registry and streams the result to
  the bastion — run twice during the lab's validation, about two
  minutes and 60 to 75 MB); `oc debug node`; image streams that merely
  point to external images.
- **Does not work**: anything that pushes — BuildConfigs with an image
  stream output, `oc new-app` from source, pulling
  `image-registry.openshift-image-registry.svc:5000/...`. None of these
  was attempted on the lab.

To enable it, the operator needs a storage backend and
`managementState: Managed`; on this lab that would mean a claim on one
of the three free local volumes (single replica, `Recreate` rollout).
Not done: it is not needed and would add one more unbounded consumer of
the shared disk. Kolla-Ansible equivalent: the optional local Docker
registry used for offline deployments.

**Pitfalls**:

- No registry means **no local copy of the images**: a pod restart
  after the kubelet has garbage-collected its image, or a node rebuild,
  needs the external registries and the proxy. A registry outage or a
  removed tag upstream becomes your outage. A mirror registry outside
  the cluster is the production answer (see the OLM file for the
  catalog side of the same concern).
- The daily `image-pruner` job has nothing to prune and completes at
  once; a completed pod named `image-pruner-*` is normal.
- `SamplesMissingTBRCredential` and the 36 image streams come from the
  samples operator, unrelated to the registry state.

**See also**: [OLM and operators](okd-olm-and-operators.md),
[Monitoring and alerting](okd-monitoring-and-alerting.md)
