# Inspect service status

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

With Kolla-Ansible you check health by looking at containers on each
controller (`docker ps`, HAProxy stats) and at the OpenStack APIs. Here there
is one more layer above the containers: each operator publishes what it
thinks of its service as **conditions** on a custom resource. Reading
conditions first saves most of the digging.

## 1. Initial symptoms

- You start a shift, or have just applied a change, and want to know whether
  the platform is healthy.
- A user reports "something is slow or failing" without detail.

## 2. Read-only investigation

Go top-down through five levels. Stop at the first level that is not healthy
and switch to the matching [runbook](../troubleshooting/README.md).

### Level 1: the control plane resource

**[READ-ONLY]**

```bash
oc get openstackcontrolplane openstack
oc get oscp openstack -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\t"}{.message}{"\n"}{end}' | column -t -s $'\t'
```

Only the conditions that are not `True`:

**[READ-ONLY]**

```bash
oc get oscp openstack -o json | jq -r '.status.conditions[] | select(.status != "True") | "\(.type): \(.reason) - \(.message)"'
```

### Level 2: the per-service custom resources

**[READ-ONLY]**

```bash
oc get keystoneapi,placementapi,glance,glanceapi,neutronapi,nova,novaapi,novascheduler,novaconductor,novametadata,novacell
oc get galera,memcached,dnsmasq,transporturl
oc get ovndbcluster,ovnnorthd
oc get rabbitmq,transporturl
```

Conditions of one service, for example Keystone:

**[READ-ONLY]**

```bash
oc get keystoneapi keystone -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}' | column -t -s $'\t'
```

### Level 3: the workloads

**[READ-ONLY]**

```bash
oc get deployments,statefulsets
oc get jobs,cronjobs
```

### Level 4: the pods

**[READ-ONLY]**

```bash
oc get pods -o wide
# Anything that is neither Running nor Completed:
oc get pods --field-selector=status.phase!=Running,status.phase!=Succeeded
# Restart counts, highest last:
oc get pods --sort-by='.status.containerStatuses[0].restartCount'
oc get events --sort-by=.lastTimestamp | tail -30
```

### Level 5: OpenStack itself

**[READ-ONLY]**

```bash
oc rsh openstackclient openstack endpoint list
oc rsh openstackclient openstack compute service list
oc rsh openstackclient openstack network agent list
oc rsh openstackclient openstack hypervisor list
```

### Data plane (when a compute node is deployed)

**[READ-ONLY]**

```bash
oc get openstackdataplanenodeset openstack-edpm
oc get openstackdataplanedeployment
```

### Everything at once

The repository smoke test runs the same checks and prints PASS or FAIL:

**[READ-ONLY]**

```bash
tests/smoke-test.sh
```

## 3. Expected observations

- Level 1: one line, `STATUS` `True`, `MESSAGE` `Setup complete`:

  ```text
  NAME        STATUS   MESSAGE
  openstack   True     Setup complete
  ```

  Every condition is `True`. The lab shows 24 of them: `Ready`, then, all
  prefixed with `OpenStackControlPlane`: `RabbitMQReady`, `MariaDBReady`,
  `MemcachedReady`, `KeystoneAPIReady`, `PlacementAPIReady`, `GlanceReady`,
  `OVNReady`, `NeutronReady`, `NovaReady`, `InfrastructureReady`,
  `DNSReadyCondition`, `CAReadyCondition`, `ClientReady`,
  `BackupConfigReady`, `InstanceHaCMReadyCondition`,
  `InstanceHaTLSReadyCondition`, `TestCMReadyCondition`,
  `OpenStackVersionInitializationReadyCondition`, and one
  `Expose<Service>Ready` per service with a Route (`ExposeKeystoneAPIReady`,
  `ExposePlacementAPIReady`, `ExposeGlanceReady`, `ExposeNeutronReady`,
  `ExposeNovaReady`). Disabled services (Horizon, Cinder, Swift, ...) have
  **no** condition at all: absence is normal.
- Level 2: every resource shows `STATUS` `True` and `MESSAGE` `Setup
  complete`. Two kinds print only an `AGE` column (`nova` and `novacell`):
  read their conditions with the `jsonpath` command instead. `KeystoneAPI`
  carries `InputReady`, `ServiceConfigReady`, `DBReady`, `DBSyncReady`,
  `BootstrapReady`, `MariaDBAccountReady`, `MemcachedReady`,
  `RabbitMqTransportURLReady`, `DeploymentReady`, `CreateServiceReady`,
  `CronJobReady`, `NetworkAttachmentsReady`, `TLSInputReady`, three
  conditions for its service account and role, and `Ready` as the summary.
  The set differs per service: `PlacementAPI`, `NeutronAPI`, `NovaAPI` and
  `GlanceAPI` add `KeystoneServiceReady` and/or `KeystoneEndpointReady`;
  `Nova` only aggregates its children (`NovaAPIReady`, `NovaSchedulerReady`,
  `NovaMetadataReady`, `NovaAllCellReady`, ...).
- Level 3: `READY` equals the desired count (`1/1`). The lab runs exactly
  these workloads:

  | Kind | Names |
  |------|-------|
  | Deployment | `keystone`, `placement`, `neutron`, `dnsmasq-dns` |
  | StatefulSet | `openstack-galera`, `openstack-cell1-galera`, `rabbitmq-server`, `rabbitmq-cell1-server`, `memcached`, `glance-default-single`, `nova-api`, `nova-scheduler`, `nova-metadata`, `nova-cell0-conductor`, `nova-cell1-conductor`, `nova-cell1-novncproxy`, `ovsdbserver-nb`, `ovsdbserver-sb`, `ovn-northd` |
  | CronJob | `keystone-cron`, `glance-db-purge`, `nova-cell0-db-purge`, `nova-cell1-db-purge` |

  There is no DaemonSet: the OVN controller only runs on the compute node,
  as a podman container, and the lab control plane has no `OVNController`
  resource. The db-sync and bootstrap Jobs are deleted once they have
  succeeded, so `oc get jobs` lists only the hourly `keystone-cron-<n>` Job
  and the data plane Jobs (`<service>-edpm-deployment-openstack-edpm`), all
  `Complete`.
- Level 4: every pod is `Running` with all containers ready, or `Completed`
  for Job pods. The API pods (`glance-default-single-0`, `neutron-...`,
  `placement-...`, `nova-api-0`, `nova-metadata-0`) and the OVN pods are
  `2/2`; the others are `1/1`. The field-selector command prints `No
  resources found`. Restart counts are `0` and stable between two looks.
- Level 5: ten endpoints, an `internal` and a `public` one for each of
  identity, placement, image, network and compute. Internal URLs have the
  form `https://<service>-internal.openstack.svc:<port>`, public ones
  `https://<service>-public-openstack.apps.<cluster domain>`. Two
  `nova-conductor` (hosts `nova-cell0-conductor-0` and
  `nova-cell1-conductor-0`) and one `nova-scheduler` are `up`; with a data
  plane, one `nova-compute` on host `edpm-compute-0.ctlplane.<cluster
  domain>` is `up`, and the agents `OVN Controller Gateway agent` and `OVN
  Metadata agent` are alive on the same host. The hypervisor list shows one
  hypervisor of type `QEMU` with host IP 192.168.122.100; its hostname is
  the name the virtual machine reported at registration, which is not
  necessarily `edpm-compute-0`.
- Data plane: the NodeSet is `True` with message `NodeSet Ready`; the
  deployment `edpm-deployment` is `True` with message `Setup complete`.
- The smoke test ends with `0 check(s) failed` (15 `PASS`, 1 `SKIP` for the
  functional test, which only runs with `--functional`).

## 4. Root cause

Why conditions are trustworthy as a first look: each operator runs a control
loop that compares the resource you declared with what exists, acts on the
difference, and then writes the result of each step into
`status.conditions`. A condition is therefore the operator's own account of
where it stopped. `Ready` is `True` only when all the others are.

The `OpenStackControlPlane` conditions are a mirror: `...KeystoneAPIReady`
copies the `Ready` condition of `KeystoneAPI/keystone`. That is why you
always go one level down to get the actual reason.

Three states exist, not two:

| `status` | `reason` | Meaning |
|----------|----------|---------|
| `True` | `Ready` | Step done |
| `False` | `Requested` | In progress or waiting for something. Normal for minutes during a rollout, a problem if it lasts |
| `False` | `Error` | The step failed; the message carries the error |
| `Unknown` | `Init` | The operator has not reached that step yet: look at an earlier condition |

## 5. Resolution

Nothing to resolve when all levels are healthy. Otherwise pick the runbook by
the first unhealthy level:

| First unhealthy level | Go to |
|-----------------------|-------|
| 1 or 2: a condition is `False` and stays so | [Reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md) |
| 3 or 4: a pod is Pending, crash-looping or cannot pull its image | [Pod Pending or CrashLoopBackOff](../troubleshooting/pod-pending-or-crashloop.md) |
| 4: Galera or RabbitMQ pod not ready | [Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md) |
| 5: API errors while pods look fine | [Network](../troubleshooting/network.md), [DNS and routing](../troubleshooting/dns-and-routing.md) |
| Data plane | [Data plane](../troubleshooting/dataplane.md) |
| `oc` itself fails | [Node and OKD](../troubleshooting/node-and-okd.md) |

## 6. Verification

Re-run level 1. Healthy means one line with `True`:

**[READ-ONLY]**

```bash
oc get openstackcontrolplane openstack
```

## 7. Risks and precautions

- Everything here is read-only.
- A `True` control plane does not prove instances can boot: conditions cover
  the control plane, not the compute nodes. Check level 5 and the data plane.
- Right after a change, conditions go `False` with reason `Requested` for a
  while. Judge by duration and by the message, not by the first glance.
- The top-level message names the first service that is not ready, which is
  not always the one you touched: while the RabbitMQ pod restarts, the
  control plane reports a Nova message for about a minute.
- A service declared with `replicas: 0` still reports `True`: conditions say
  "what was asked is done", not "the API answers".
- `oc rsh openstackclient` runs as OpenStack admin. Read-only commands are
  safe; anything else changes the cloud.
