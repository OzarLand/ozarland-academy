# Storage problems

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) for scenarios A and B (Pending claim reproduced with a throwaway claim; a `Released` volume produced, recovered and recycled for real); scenario C was validated read-only: the disk was not filled, and `crictl rmi --prune`, the image deletion and the clean-up of failed pods were not executed

The lab uses the simplest possible storage: a fixed number of directories on
the OKD node, each published as a PersistentVolume (PV) of class
`local-storage`. There is no provisioner: when the volumes are used up, no
new one appears. That makes the binding between claims and volumes easy to
observe, and it produces three typical faults.

Where things are:

| Object | Meaning |
|--------|---------|
| PersistentVolume `local-storage-NN` | A directory `/var/lib/openstack-lab-pv/pvNN` on the node |
| PersistentVolumeClaim (PVC) | A request for storage by a pod, for example `mysql-db-openstack-galera-0` |
| StorageClass `local-storage` | The label that lets a claim find these volumes |

Consumers in the lab: two Galera servers, two RabbitMQ servers, two OVN
databases and Glance: seven volumes out of the twelve created by default.

## Scenario A: PVC Pending, no volume available

### 1. Initial symptoms

- A pod of a stateful service is `Pending`.
- `...MariaDBReady`, `...RabbitMQReady`, `...OVNReady` or `...GlanceReady`
  stays `False`.
- Typically after enabling an extra service, scaling a stateful one, or
  redeploying the control plane on a cluster that was used before.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get pvc
oc describe pvc <claim> | sed -n '/^Events:/,$p'
oc get pv -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,SIZE:.spec.capacity.storage,CLASS:.spec.storageClassName,CLAIM:.spec.claimRef.name
oc get pv --no-headers | awk '{print $5}' | sort | uniq -c
oc get storageclass
oc get oscp openstack -o jsonpath='{.spec.storageClass}{"\n"}'
oc get pvc <claim> -o jsonpath='{.spec.storageClassName} {.spec.resources.requests.storage}{"\n"}'
```

### 3. Expected observations

On a healthy lab: twelve volumes of 10Gi, seven `Bound` and five
`Available`, all with reclaim policy `Retain` (the `RECLAIMPOLICY` column of
`oc get storageclass` says `Delete`, but that is only a default for
dynamically created volumes and does not apply here). The seven claims are
`mysql-db-openstack-galera-0`, `mysql-db-openstack-cell1-galera-0`,
`persistence-rabbitmq-server-0`, `persistence-rabbitmq-cell1-server-0`,
`ovndbcluster-nb-etc-ovn-ovsdbserver-nb-0`,
`ovndbcluster-sb-etc-ovn-ovsdbserver-sb-0` and
`glance-glance-default-single-0`. A claim shows the capacity of the volume
it got (10Gi), not what it asked for (the Galera claims ask for 5Gi).

In a fault, one of:

- No PV is `Available`: all are `Bound` or `Released`. The pod event says
  `0/1 nodes are available: 1 node(s) didn't find available persistent
  volumes to bind`.
- The claim asks for a class that does not exist (typo in `storageClass`).
- The claim asks for more than any volume offers (request above the PV
  size, 10Gi by default).
- The PVC shows `WaitForFirstConsumer`: that is normal while no pod uses it
  yet, not a fault.

### 4. Root cause

A claim binds to one whole volume that has the same class, enough capacity
and a compatible access mode. Static volumes are never split or created on
demand. `Released` volumes do not count: with the `Retain` policy a volume
that once belonged to a claim is kept aside, data intact, until an
administrator decides what to do with it.

### 5. Resolution

Wrong class or size: fix the control plane resource (`storageClass`,
`storageRequest`). A PVC cannot be edited to another class; after fixing the
declaration, delete the Pending claim so that it is recreated.

**[CHANGE]** Safe only for a claim that was never bound (`Pending`, no
`VOLUME`).

```bash
oc delete pvc <pending-claim>
```

Not enough volumes: create more by raising `STORAGE_PV_COUNT` in `lab.env`
and re-running the platform step (idempotent, existing volumes untouched):

**[CHANGE]**

```bash
scripts/bastion/04-platform-services.sh
```

Volumes are `Released`: see scenario B.

### 6. Verification

**[READ-ONLY]**

```bash
oc get pvc                       # all Bound
oc get pods | grep -v 'Running\|Completed'
oc get openstackcontrolplane openstack
```

### 7. Risks and precautions

- Never delete a `Bound` PVC to fix a `Pending` one.
- Adding volumes consumes no space by itself, but all volumes share the node
  root disk: the declared sizes are not enforced (see scenario C).

## Scenario B: PV Released

### 1. Initial symptoms

- After deleting a control plane (or a claim), `oc get pv` shows volumes in
  `Released` and new claims stay `Pending`.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get pv | grep Released
oc get pv <pv> -o jsonpath='{.spec.claimRef.namespace}/{.spec.claimRef.name}  {.spec.local.path}{"\n"}'
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc debug node/${node} --quiet -- chroot /host du -sh /var/lib/openstack-lab-pv/pv01
oc debug node/${node} --quiet -- chroot /host ls -la /var/lib/openstack-lab-pv/pv01
```

### 3. Expected observations

- The volume still names its former claim in `claimRef`.
- The directory still contains the data (a MariaDB data directory, RabbitMQ
  mnesia files, OVN database files or Glance images).
- If the claim was recreated in the meantime (a StatefulSet does it by
  itself), the new claim has the same name but is bound to a **different**,
  empty volume. Observed on the lab after deleting the claim of a RabbitMQ
  server: the new `persistence-rabbitmq-cell1-server-0` took another free
  volume and the old one stayed `Released` with the old data.

### 4. Root cause

`Retain` is deliberate: deleting a claim must not silently destroy a
database. The price is that reuse is manual. Kubernetes will not hand a
volume with someone else's data to a new claim.

### 5. Resolution

Decide per volume: **recover** or **recycle**.

Recover (reattach the same data to the same service): keep the files and
keep the name of the claim in the reference, but remove the identity of the
old claim object (`uid` and `resourceVersion`). The volume becomes
`Available` and stays reserved: only a claim with that namespace and name
can bind to it. Verified on the lab: a new claim of the same name bound to
exactly this volume and found its data.

**[CHANGE]**

```bash
oc patch pv <pv> --type=json -p '[{"op":"remove","path":"/spec/claimRef/uid"},{"op":"remove","path":"/spec/claimRef/resourceVersion"}]'
```

This only helps while no claim of that name exists. If the service already
runs on a new empty volume, you have to stop it and delete that claim first,
which is an outage of the service: decide whether the old data is worth it.

Removing the whole `claimRef` instead also makes the volume `Available`, but
for anyone: with several free volumes nothing guarantees which one a claim
picks.

Recycle (give the volume to anyone, empty): wipe the directory, then clear
the reference.

**[DESTRUCTIVE]** Permanently deletes the data of the former owner. Check the
`claimRef` and the path twice. There is no undo.

```bash
pv=local-storage-07
path=$(oc get pv ${pv} -o jsonpath='{.spec.local.path}')
echo "About to wipe ${path} formerly used by $(oc get pv ${pv} -o jsonpath='{.spec.claimRef.name}')"
oc debug node/${node} --quiet -- chroot /host bash -c "find '${path}' -mindepth 1 -delete"
oc patch pv ${pv} --type=json -p '[{"op":"remove","path":"/spec/claimRef"}]'
```

Never clear the reference without wiping when the volume will go to a
different service: Galera starting on a RabbitMQ directory, or on another
cluster's data, fails in confusing ways.

### 6. Verification

**[READ-ONLY]**

```bash
oc get pv                         # Available or Bound, none Released
oc get pvc
oc debug node/${node} --quiet -- chroot /host ls -A /var/lib/openstack-lab-pv/pv07   # empty after a recycle
```

### 7. Risks and precautions

- The wipe is the only command in this lab that destroys OpenStack data
  directly. Run it only on `Released` volumes, one at a time.
- If the goal is to keep a database, back it up before deleting anything
  (see [backup and restore](../lifecycle/05-backup-and-restore.md)).

## Scenario C: node disk full

### 1. Initial symptoms

- Pods are `Evicted` with reason `DiskPressure`, or the node has the
  condition `DiskPressure=True`.
- Services log `No space left on device`; Galera or RabbitMQ stop accepting
  writes; image uploads to Glance fail.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc describe node | sed -n '/Conditions:/,/Addresses:/p'
node=$(oc get nodes -o jsonpath='{.items[0].metadata.name}')
oc debug node/${node} --quiet -- chroot /host df -h /var /sysroot
oc debug node/${node} --quiet -- chroot /host bash -c 'du -xsh /var/lib/openstack-lab-pv/* | sort -h | tail'
oc debug node/${node} --quiet -- chroot /host bash -c 'du -xsh /var/lib/containers /var/log 2>/dev/null'
oc rsh openstackclient openstack image list --long -c Name -c Size
```

### 3. Expected observations

- One filesystem holds everything: container images, container logs, and all
  persistent volumes. `df` shows the same device for `/var` and `/sysroot`.
- On the freshly deployed lab the 150 GB disk is about a quarter full,
  almost all of it container images; the volume directories are small. The
  consumer that grows is the Glance volume (uploaded images).
- No node condition is `True` except `Ready`.

### 4. Root cause

A `local` volume is a directory. Its declared capacity (10Gi) is used for
matching claims, not enforced as a quota. Any service can fill the node
disk, and when the disk passes the kubelet eviction threshold the node
starts evicting pods, including healthy ones.

### 5. Resolution

Free space where it is safe:

**[CHANGE]** Deletes OpenStack images you no longer need.

```bash
oc rsh openstackclient openstack image delete <image>
```

**[CHANGE]** Removes unused container images on the node.

```bash
oc debug node/${node} --quiet -- chroot /host crictl rmi --prune
```

Then let the node recover (the `DiskPressure` condition clears by itself)
and clean up evicted pod records:

**[CHANGE]**

```bash
oc delete pods --field-selector=status.phase=Failed
```

If the disk is simply too small, grow the node volume in the host cloud and
the filesystem on the node; that procedure belongs to the infrastructure
documentation.

### 6. Verification

**[READ-ONLY]**

```bash
oc describe node | grep -A1 DiskPressure
oc get pods | grep -v 'Running\|Completed'
oc get openstackcontrolplane openstack
```

### 7. Risks and precautions

- Do not delete files inside a volume directory of a running database to
  make room.
- After a disk-full event, check Galera and RabbitMQ explicitly
  ([runbook](galera-and-rabbitmq.md)): both may have stopped uncleanly.
- etcd lives on the same disk. A full disk can take the whole cluster down,
  not only OpenStack: keep at least 20% free.
