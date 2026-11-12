# OLM and the OpenStack operators

> Status: every command was run on the lab (single-node OKD 4.22,
> operators 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12

The OpenStack operators are installed and kept in place by the Operator
Lifecycle Manager (OLM) of OKD. This file records the chain of objects
from the catalog image to the running operator pods, how to pin the
catalog, how to read operator logs and restart an operator without
touching the services, how to tune or switch off individual operators,
what resource types they own, and what they leave behind. The concepts
are in
[Operators, CRDs and reconciliation](../concepts/03-operators-crds-and-reconciliation.md).
Commands run on the bastion as the cluster administrator.

## Entries

### How are the OpenStack operators installed, and how do I check every link of the chain?

**Context**: first look; an operator pod is missing; "which version of
the operators is this?".

**How**:

**[READ-ONLY]**

```bash
NS=openstack-operators
oc get catalogsource -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,IMAGE:.spec.image,POLL:.spec.updateStrategy.registryPoll.interval,STATE:.status.connectionState.lastObservedState'
oc get operatorgroup -n $NS
oc get subscription -n $NS -o custom-columns='NAME:.metadata.name,PKG:.spec.name,CHANNEL:.spec.channel,SOURCE:.spec.source,APPROVAL:.spec.installPlanApproval,INSTALLED:.status.installedCSV,STATE:.status.state'
oc get installplan -n $NS
oc get csv -n $NS
oc get packagemanifest -n $NS openstack-operator -o jsonpath='{.status.channels[*].name} {.status.channels[*].currentCSV}{"\n"}'
oc get openstack -n $NS
oc get deploy -n $NS -o custom-columns='NAME:.metadata.name,OWNER:.metadata.ownerReferences[*].kind,REPLICAS:.spec.replicas,REQ:.spec.template.spec.containers[*].resources.requests.memory'
oc get co operator-lifecycle-manager operator-lifecycle-manager-catalog operator-lifecycle-manager-packageserver marketplace
oc get pods -n openshift-operator-lifecycle-manager; oc get pods -n openshift-marketplace
```

**Observed on the lab** (2026-11-12):

```text
CatalogSource   openstack-operators/openstack-operator-index   grpc   READY   no polling
                openshift-marketplace/community-operators      READY   poll 240m   (the only default source left enabled)
OperatorGroup   openstack
Subscription    openstack-operator   channel alpha   source openstack-operator-index   approval Manual
                installed openstack-operator.v0.8.0   state AtLatestKnown
InstallPlan     install-<id>   openstack-operator.v0.8.0   Manual   approved
CSV             openstack-operator.v0.8.0   Succeeded
OpenStack       openstack   DEPLOYED OPERATOR COUNT 21   STATUS True
Deployments     openstack-operator-controller-init      owner ClusterServiceVersion   128Mi
                openstack-operator-controller-manager   owner OpenStack               512Mi
                infra-operator-controller-manager       owner OpenStack               512Mi
                19 more <service>-operator-controller-manager   owner OpenStack       256Mi each
OLM itself      4 cluster operators Available; pods catalog-operator, olm-operator, packageserver, package-server-manager
```

**Why / how it works**: six links, each visible as an object.

1. The **CatalogSource** runs a pod from the catalog (index) image; the
   pod serves the list of available operator bundles over gRPC.
2. The **Subscription** says "package `openstack-operator`, channel
   `alpha`, from that catalog".
3. OLM resolves it into an **InstallPlan**; with `Manual` approval
   nothing is installed or upgraded until someone approves the plan (the
   installation script approves the first one).
4. The plan creates the **ClusterServiceVersion** (CSV), which carries
   one Deployment: `openstack-operator-controller-init`.
5. That initialisation operator watches the **OpenStack** resource
   (created by the installation script, empty spec) and
6. creates the CRDs, the RBAC and the 21 service operator Deployments.

So OLM manages one small operator, and that operator manages the
others: the service operators are not OLM objects, and a new version of
the bundle replaces them all together. Kolla-Ansible equivalent: the
`kolla-ansible` package version and the image tag in `globals.yml`;
there is no running component that corresponds to OLM.

**Pitfalls**:

- `oc get csv -A` shows the CSV in every namespace (78 copies): the
  OperatorGroup targets all namespaces and OLM copies the CSV as a
  marker. Only the one in `openstack-operators` is real.
- There is no `placement-operator` or `rabbitmq-operator` pod: those
  controllers live in other operators (the count is 21 Deployments
  besides the initialisation operator, for 31 API groups).
- `Manual` approval is what keeps the lab on a known version. An
  InstallPlan waiting with `APPROVED false` is an upgrade proposal, not
  an error; approving it is the start of the update procedure
  (lifecycle guide), not a routine click.
- A Subscription in state `UpgradePending` for a long time with no
  InstallPlan usually means the catalog pod is unhealthy: check link 1
  first.

**See also**:
[OpenStack operators installation](../installation/04-openstack-operators.md),
[Operators, CRDs and reconciliation](../concepts/03-operators-crds-and-reconciliation.md)

### Is the catalog pinned to a digest, and how do I move a running lab from a tag to a digest?

**Context**: the catalog image decides which operator versions a
rebuild or an upgrade proposal will offer. A moving tag
(`18-stable-latest`) changes under your feet; a digest does not.

**How**:

**[READ-ONLY]** — compare what is declared with what runs.

```bash
NS=openstack-operators; CS=openstack-operator-index
oc get catalogsource -n $NS $CS -o jsonpath='{.spec.image}{"\n"}'
oc get pods -n $NS -l olm.catalogSource=$CS \
  -o custom-columns='IMAGE:.spec.containers[0].image,RUNNING:.status.containerStatuses[0].imageID,PULL:.spec.containers[0].imagePullPolicy,STARTED:.status.startTime'
grep OPENSTACK_OPERATOR_INDEX lab.env config/lab.env.example
```

**[CHANGE]** — pin the CatalogSource to the digest that is **already
running**, then make the lab configuration say the same. The catalog
pod is replaced; operators and services are not touched.

```bash
RUN=$(oc get pods -n $NS -l olm.catalogSource=$CS -o jsonpath='{.items[0].status.containerStatuses[0].imageID}' | grep -o 'sha256:[0-9a-f]*')
REPO=$(oc get catalogsource -n $NS $CS -o jsonpath='{.spec.image}' | cut -d: -f1)
oc patch catalogsource -n $NS $CS --type=merge -p "{\"spec\":{\"image\":\"${REPO}@${RUN}\"}}"
oc get catalogsource -n $NS $CS -o jsonpath='{.status.connectionState.lastObservedState}{"\n"}'
oc get subscription,installplan,csv -n $NS
sed -i -E "s#^OPENSTACK_OPERATOR_INDEX=.*#OPENSTACK_OPERATOR_INDEX=${REPO}@${RUN}#" lab.env
```

**Observed on the lab** (2026-11-12):

```text
before   spec.image  quay.io/openstack-k8s-operators/openstack-operator-index:18-stable-latest
         running     ...openstack-operator-index@sha256:<digest A>     pull policy Always
         config/lab.env.example pins sha256:<digest A>: identical to the running one
patch    new catalog pod Running and CatalogSource READY after 19 s
after    spec.image  ...openstack-operator-index@sha256:<digest A>     pull policy IfNotPresent
         Subscription AtLatestKnown, still openstack-operator.v0.8.0; same single InstallPlan; CSV Succeeded
         package manifest: channel alpha -> openstack-operator.v0.8.0
```

The lab had been installed with the tag; it now runs pinned, with the
bastion's `lab.env` updated so that a re-run of the operator step
applies the same value.

**Why / how it works**: with a tag, the catalog pod pulls with policy
`Always`: every restart of that pod (node reboot, eviction) may fetch a
newer catalog, and the Subscription then proposes a new InstallPlan.
Nothing upgrades by itself thanks to `Manual` approval, but a
**rebuild** of the lab would install whatever the tag points to that
day. With a digest the content is immutable and the pull policy becomes
`IfNotPresent`. The move is safe when the digest is the running one:
the new pod serves the same bundles, so OLM resolves the same CSV.
Kolla-Ansible equivalent: pinning `openstack_tag` to a dated tag or a
digest instead of a moving branch tag.

**Pitfalls**:

- Pinning to a **different** digest is an upgrade proposal: OLM may
  create a new InstallPlan. Compare digests before patching (the
  commands above refuse nothing by themselves).
- The digest must be recorded outside the cluster (the lab
  configuration): the CatalogSource is recreated from `lab.env` by the
  installation step.
- A digest pins the catalog, not the service images: those are listed
  in the bundle and resolved into the `OpenStackVersion` resource, by
  digest as well.
- Without a mirror, the pinned image must stay available upstream; old
  catalog images of a moving branch can be garbage-collected by the
  registry. Mirroring the catalog and the bundle images is the
  production answer.
- The community catalog (`community-operators`) still polls every four
  hours and restarts its pod on change; it is unused by the lab and can
  be disabled in the `OperatorHub` resource to save memory.

**See also**:
[OpenStack operators installation](../installation/04-openstack-operators.md),
[The image registry is "Removed"](okd-storage.md#the-image-registry-is-removed-what-does-that-imply)

### How do I read an operator's logs, and when do operators actually reconcile?

**Context**: a resource stays not Ready; a manual change was not
reverted when expected; "is the operator doing anything?".

**How**:

**[READ-ONLY]**

```bash
NS=openstack-operators
# which operator handles which kind: the kind's API group names it (keystone.openstack.org -> keystone-operator)
oc logs -n $NS deploy/keystone-operator-controller-manager --since=1h | tail -20
# one line per event, tab-separated: time, level, logger, message, JSON context
oc logs -n $NS deploy/keystone-operator-controller-manager --since=6h \
  | awk -F'\t' '$4 == "Reconciling Service" {print substr($1,12,5), $3}' | uniq -c
# activity per hour since the pod started
oc logs -n $NS deploy/glance-operator-controller-manager | awk -F'\t' 'length($1) > 18 {print substr($1,12,2)}' | sort | uniq -c
# errors only
oc logs -n $NS deploy/openstack-operator-controller-manager --since=6h | grep -P '\tERROR\t' | tail
```

**Observed on the lab** (2026-11-12, operator pods started at 01:06 UTC
after the night reboot):

```text
glance, mariadb, neutron, ovn operators:  all their log lines are in the first hour (01:xx); nothing in the 11 hours since
nova operator:                            01:xx, 07:xx (a data plane change), 11:xx
openstack operator:                       01:xx, 06:xx, 07:xx, 11:xx, 12:xx — each burst matches a change made to the control plane
keystone operator:                        "Reconciling Service" at 07:01:00, 08:01:00, 09:01:00, 10:01:00 ... every hour at minute 1,
                                          plus bursts at each Keystone change (12:28, the resources exercise)
```

**Why / how it works**: an operator reconciles when something it
**watches** changes: its own resource, or an object it owns
(Deployment, Secret, Job...). It does not poll. An idle control plane
gives silent operators: over 11 hours four of them logged nothing at
all, so no periodic full pass happened in that window. Keystone's
hourly reconcile is not a timer either: it coincides with the
`keystone-cron` CronJob (schedule `1 * * * *`, trust flush) whose Jobs
the KeystoneAPI resource owns. Consequences: a manual change to an
owned object is reverted **at once** (the change itself is the event),
while a change to something the operator does not watch (an OpenStack
database row, an endpoint in the Keystone catalog, a file in a pod) is
never noticed until another event triggers a reconcile. Kolla-Ansible
equivalent: nothing reconciles; drift stays until the next
`kolla-ansible reconfigure`.

**Pitfalls**:

- "No log line" is the normal state, not a hung operator. To prove an
  operator is alive, look at its lease (next entry) or touch its
  resource with a harmless annotation and watch the log.
- To force a reconcile, annotate the resource
  (`oc annotate keystoneapi keystone -n openstack kb/touch="$(date +%s)" --overwrite`
  then remove the annotation); do not restart the operator for that.
- The `openstack-operator` log mixes the control plane controller, the
  data plane controllers and the admission webhooks (`...-resource`
  loggers: "validate update", "Defaulting for ..."). Webhook lines
  appear for every `oc apply`, including dry runs, and prove only that
  someone submitted the object. Checked on the lab: an "update" logged
  at 11:37 that nobody remembered was, in the API audit log, a
  `--dry-run=server` patch (`dryRun=All` in the request URI).
- Logs are lost with the pod (restart, node reboot keeps only the
  previous container: `oc logs --previous`). The reboot of the night
  erased everything before 01:06.

**See also**: [Logs](../operations/02-logs.md),
[Manual changes reverted](../troubleshooting/manual-changes-reverted.md),
[Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md)

### How do I restart a service operator safely, and what does leader election do?

**Context**: an operator is suspected stuck (resource not progressing,
no log after a change), or it was OOM-killed.

**How**:

**[READ-ONLY]**

```bash
NS=openstack-operators
oc get lease -n $NS -o custom-columns='NAME:.metadata.name,HOLDER:.spec.holderIdentity,RENEW:.spec.renewTime,DURATION:.spec.leaseDurationSeconds,TRANSITIONS:.spec.leaseTransitions'
```

**[CHANGE]** — restarts one operator; the services it manages keep
running.

```bash
oc delete pod -n $NS -l openstack.org/operator-name=keystone   # or: oc rollout restart deploy/keystone-operator-controller-manager -n $NS
oc rollout status -n $NS deploy/keystone-operator-controller-manager --timeout=120s
oc logs -n $NS deploy/keystone-operator-controller-manager | grep -E 'leader|Starting workers' | head
oc get keystoneapi -n openstack; oc get oscp -n openstack
```

**Observed on the lab** (2026-11-12):

```text
22 leases, one per operator, renewed every few seconds; duration 30 s (15 s for four of them); 4 to 11 transitions each
12:37:50  pod deleted
12:37:51  new pod: "attempting to acquire leader lease openstack-operators/<id>.openstack.org..."
12:38:02  new pod Ready (12 s)
12:38:24  "successfully acquired lease" (34 s after the deletion), then "Starting workers" for 4 controllers
          12 reconciles of KeystoneAPI in the following seconds, all ending Ready
KeystoneAPI True "Setup complete"; OpenStackControlPlane True
pods of the openstack namespace: same names, same restart counts as before
```

**Why / how it works**: each operator takes a **Lease** object before
starting its controllers, so that two replicas never act at once. A
deleted pod does not release its lease: the newcomer waits until the
lease expires (30 seconds), then starts its workers and reconciles
every resource it manages once — a full pass, which is the practical
way to "resync" one operator. The operator is control, not data path:
while it is down, Keystone serves requests as before; only changes
wait. Kolla-Ansible equivalent: none (no long-running controller).

**Pitfalls**:

- "Ready" is not "working": for half a minute after a restart the pod
  is Ready but idle, waiting for the lease. Do not conclude that the
  restart did not help before the "Starting workers" line.
- The full pass after restart re-applies everything the operator owns:
  manual changes that had gone unnoticed are reverted at that moment.
  After a node reboot, all operators do this at once.
- Restarting `openstack-operator-controller-manager` also interrupts
  the admission webhooks for the OpenStackControlPlane and data plane
  kinds: `oc apply` on those kinds fails for a few seconds.
- A high transition count is not an alarm on this lab (every node
  reboot adds one or more); a count that grows while the node is up
  means the operator loses its lease: API latency or operator restarts.

**See also**:
[Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md),
[Cluster health and etcd](okd-cluster-health-and-etcd.md)

### How do I switch off or resize individual operators (`operatorOverrides`)?

**Context**: 21 operators run although the lab deploys a handful of
services; together they request 6 GiB of memory (workloads file). Or
one operator needs more memory than its 512 MiB limit.

**How**:

**[READ-ONLY]**

```bash
oc explain openstack.spec.operatorOverrides --recursive
oc get openstack -n openstack-operators openstack -o jsonpath='{.spec}{"\n"}'
```

**[CHANGE]** — scale the Watcher operator to zero (Watcher is not
deployed on the lab).

```bash
oc patch openstack -n openstack-operators openstack --type=merge \
  -p '{"spec":{"operatorOverrides":[{"name":"watcher","replicas":0}]}}'
oc get openstack -n openstack-operators
oc get deploy -n openstack-operators watcher-operator-controller-manager
```

**[CHANGE]** — revert.

```bash
oc patch openstack -n openstack-operators openstack --type=json -p '[{"op":"remove","path":"/spec/operatorOverrides"}]'
```

**Observed on the lab** (2026-11-12):

```text
fields      operatorOverrides[]: name (openstack, barbican, cinder, designate, ...), replicas,
            controllerManager.resources (requests, limits), tolerations
before      spec {}                      DEPLOYED OPERATOR COUNT 21
patch       watcher Deployment at 0 replicas after 3 s; no other Deployment changed (generation and replicas compared)
            DEPLOYED OPERATOR COUNT 20, STATUS True; node CPU limits 15010m -> 14510m
manual      "oc scale ... --replicas=1" on the Deployment: back to 0 within 20 s (the override wins)
revert      watcher pod Ready after 15 s; count 21; spec {}; OpenStackControlPlane still Ready
```

**Why / how it works**: the service operator Deployments are owned by
the `OpenStack` resource; the initialisation operator rewrites them
from its built-in defaults plus `operatorOverrides`. That is the only
durable way to change them: editing a Deployment directly is reverted
(observed), exactly like editing a service Deployment under the control
plane. Each switched-off operator frees one pod, 256 MiB of memory
requests (about 60 MiB of real use) and 500m of CPU limits.
Kolla-Ansible equivalent: `enable_<service>: "no"` removes the
containers; here the service and its operator are two separate
switches.

**Pitfalls**:

- An operator at zero replicas leaves its CRDs in place: resources of
  that kind can still be created and will simply never progress, with
  no error. Switch an operator off only for services you do not deploy,
  and back on **before** enabling the service in the control plane.
- Do not switch off `openstack`, `infra`, `mariadb`, `rabbitmq`-related
  or any operator whose kinds exist in the cluster (list in the next
  entry): running services survive, but nothing reconciles them any
  more, and the control plane status freezes.
- Switching off on a lab is a memory optimisation that moves the
  installation away from the tested shape; it was reverted here and is
  listed as an open question (which set is safe to disable for this
  topology).
- `controllerManager.resources` restarts the operator (34 seconds of
  lease wait, previous entry).

**See also**:
[How do I read the node's requests and limits accounting](okd-workloads-and-resources.md#how-do-i-read-the-nodes-requests-and-limits-accounting),
[Enable a service](../operations/05-enable-a-service.md)

### Which resource types do the operators own, and which exist on this lab?

**Context**: finding the right kind to look at; writing RBAC or a
backup list; checking that nothing unexpected was created.

**How**:

**[READ-ONLY]**

```bash
oc get crd -o name | grep -c 'openstack.org'
oc get crd -o name | grep 'openstack.org' | sed -E 's/.*\.([a-z]+\.openstack\.org)$/\1/' | sort | uniq -c
oc get csv -n openstack-operators openstack-operator.v0.8.0 -o jsonpath='{range .spec.customresourcedefinitions.owned[*]}{.kind}{"\n"}{end}'
# every kind that has at least one object
for r in $(oc api-resources --verbs=list --namespaced -o name | grep 'openstack.org'); do
  n=$(oc get "$r" -A --no-headers 2>/dev/null | wc -l); [ "$n" -gt 0 ] && echo "$n $r"; done
```

**Observed on the lab** (2026-11-12): 104 CRDs in 31 API groups; the
CSV declares only one of them (`OpenStack`), the other 103 are created
by the initialisation operator. 36 kinds have objects:

```text
core        1 openstackcontrolplanes   1 openstackversions   1 openstacks (operator.openstack.org)
dataplane   1 openstackdataplanenodesets   7 openstackdataplanedeployments   37 openstackdataplaneservices
database    2 galeras   7 mariadbdatabases   9 mariadbaccounts   2 galerabackups   1 openstackbackupconfigs
messaging   2 rabbitmqs   4 transporturls   1 memcacheds
identity    1 keystoneapis   4 keystoneservices   4 keystoneendpoints
compute     1 nova   1 novaapis   2 novacells   2 novaconductors   1 novaschedulers   1 novametadata   1 novanovncproxies
            1 placementapis
image       1 glances   1 glanceapis
network     1 neutronapis   2 ovndbclusters   1 ovnnorthds   1 netconfigs   1 ipsets   1 reservations   1 dnsmasqs   4 dnsdata
client      1 openstackclients
```

Groups with CRDs but no object (operators running for nothing here):
barbican, cinder, designate, heat, horizon, instanceha, ironic, manila,
octavia, redis, swift, telemetry, test, topology, watcher, baremetal.

**Why / how it works**: the single `OpenStackControlPlane` is the
resource an operator edits; the `openstack-operator` expands it into
one resource per service (`KeystoneAPI`, `Nova`, `Galera`...), and each
service operator expands its own into sub-resources (`NovaCell`,
`MariaDBDatabase`, `KeystoneEndpoint`, `TransportURL`) and finally into
Kubernetes objects. The four of each of services, endpoints and
transport URLs correspond to the four OpenStack services deployed with
an API (Nova, Placement, Glance, Neutron) — Keystone registers itself.
Kolla-Ansible equivalent: the inventory groups and `globals.yml`
switches; there is no object per database account or endpoint.

**Pitfalls**:

- Because the CSV owns one CRD only, **uninstalling the operator
  through OLM does not remove the other 103 CRDs** nor their objects;
  conversely, deleting a CRD by hand deletes every object of that kind
  at once, and with them the running services. Never delete an
  `openstack.org` CRD on a live platform.
- Only the top resources are yours to edit (`OpenStackControlPlane`,
  node sets, deployments, `OpenStackVersion`, backups). Editing a
  generated resource (`KeystoneAPI`, `NovaCell`) is reverted by the
  operator above it.
- The 37 `openstackdataplaneservices` are a catalogue of available
  steps, not 37 deployed services; the 7 deployments are history (each
  run stays as an object, see the garbage entry).
- `oc get all` shows none of these kinds. Use the loop above or
  `oc get openstackcontrolplane,openstackdataplanenodeset`.

**See also**:
[How do I let someone read OpenStack resources](okd-access-and-security.md),
[The control plane custom resource](../concepts/03-operators-crds-and-reconciliation.md)

### What garbage accumulates (old ReplicaSets, Jobs, completed pods), and what may I clean?

**Context**: `oc get pods` is full of `Completed`; "can I delete all
this?".

**How**:

**[READ-ONLY]**

```bash
oc get rs -A --no-headers | awk '$3 == 0 {c[$1]++} END {for (n in c) print c[n], n}' | sort -rn | head
oc get deploy -n openstack keystone -o jsonpath='{.spec.revisionHistoryLimit}{"\n"}'
oc get pods -A --no-headers | awk '$4 == "Completed" || $4 == "Error" {c[$1" "$4]++} END {for (n in c) print c[n], n}' | sort -rn
oc get jobs -n openstack -o custom-columns='NAME:.metadata.name,OK:.status.succeeded,TTL:.spec.ttlSecondsAfterFinished,OWNER:.metadata.ownerReferences[0].kind,CREATED:.metadata.creationTimestamp'
oc get cronjob -A -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,SCHEDULE:.spec.schedule,KEEP_OK:.spec.successfulJobsHistoryLimit,KEEP_FAILED:.spec.failedJobsHistoryLimit'
oc get oscp openstack -n openstack -o jsonpath='{.spec.keystone.template.preserveJobs}{"\n"}'
```

**Observed on the lab** (2026-11-12, 16 hours after installation):

```text
ReplicaSets at 0:   51 in the cluster, 23 in openstack (6 for keystone alone); revisionHistoryLimit 10
Completed pods:     33 in openstack, 1 in openstack-operators (the bundle unpack job), a dozen platform installer pods
Jobs in openstack:  33, none with a TTL
   21 owned by OpenStackDataPlaneDeployment (one per service per deployment run: bootstrap-..., nova-..., ovn-...)
   12 owned by a CronJob: keystone-cron x3, db purge x3, Galera backups (scheduled and manual)
CronJobs:           keystone-cron "1 * * * *", glance-db-purge "1 0 * * *", nova-cell0/cell1-db-purge "0 0 * * *",
                    backup-openstack and backup-openstack-cell1 "@daily"; keep 3 successful, 1 failed
preserveJobs:       false (the database sync and bootstrap jobs of the services were already removed by the operators)
```

**Why / how it works**: three populations with three rules.

- **Old ReplicaSets** are the rollback history of Deployments: one per
  past pod template, kept up to `revisionHistoryLimit` (10), empty and
  free. Kubernetes prunes them itself.
- **CronJob runs** are pruned by the CronJob (three successes kept).
  Jobs created by hand from a CronJob (`oc create job --from=cronjob/...`)
  belong to nobody's history and stay until deleted.
- **Data plane Jobs** are the Ansible runs of each
  OpenStackDataPlaneDeployment: they hold the only copy of the Ansible
  output (`oc logs job/...`) and are deleted with their deployment
  object, never by time.

Service jobs (`keystone-db-sync`, `nova-cell1-cell-mapping`...) are
deleted on success unless `preserveJobs: true` is set on the service,
which is the switch to keep them for debugging. Kolla-Ansible
equivalent: none of this is kept; bootstrap containers are removed and
the Ansible output is on the deployment host's terminal.

**[CHANGE]** — what is safe to clean, when the list bothers you (not
run on the lab: these objects are the trace of earlier exercises and
cost nothing).

```bash
# old data plane runs: delete the deployment object, its jobs and pods follow
oc get openstackdataplanedeployment -n openstack
oc delete openstackdataplanedeployment -n openstack <old-deployment>
# jobs created by hand from a CronJob
oc delete job -n openstack <manual-job>
```

**Pitfalls**:

- Do not bulk-delete with `--field-selector status.phase=Succeeded`
  across namespaces: the platform's `installer-*` and `revision-pruner-*`
  pods in `openshift-kube-*` are managed by their operators, and the
  data plane job pods are your deployment logs.
- Keep at least the **last successful** data plane deployment of each
  node set: it documents what was applied, and the node set status
  refers to it.
- The 16-hour-old `Error` pods in `openshift-kube-scheduler` and
  `openshift-kube-controller-manager` are installer pods interrupted by
  a node reboot; a later revision succeeded. Harmless.
- Completed pods keep their logs on the node's disk until deleted
  (bounded by the per-container log rotation); the cost is small but
  not zero.

**See also**: [Data plane troubleshooting](../troubleshooting/dataplane.md),
[Backup and restore](../lifecycle/05-backup-and-restore.md)
