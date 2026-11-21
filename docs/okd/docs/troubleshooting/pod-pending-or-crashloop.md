# Pod Pending, CrashLoopBackOff or ImagePullBackOff

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) except the `nodeSelector` removal (the lab declares none), enabling `telemetry` and the image override (not executed: the pull errors were reproduced with throwaway pods instead)

## In short

- `Pending`: nothing has started, there is no log. The answer is in the
  events of the pod.
- `CrashLoopBackOff`: read `oc logs --previous` before deleting the pod.
  After a `customServiceConfig` change the cause is usually a value of
  the wrong type; revert it at the source.
- API services behind Apache do not crash: the pod stays `Running` and
  never becomes ready, with a misleading log.
- `ImagePullBackOff`: the event shows the registry's answer. Deleting
  the pod does not help.
- The operator is not in error in any of these cases: it waits for the
  pod, for ever.

A pod status is the Kubernetes view of a container, where a Kolla operator
would look at `docker ps`. Three statuses cover most failures. They mean
very different things:

| Status | The container... | Look at |
|--------|------------------|---------|
| `Pending` | has not been placed or cannot be prepared | Events of the pod |
| `ImagePullBackOff` / `ErrImagePull` | cannot be downloaded | Events of the pod |
| `CrashLoopBackOff` / `Error` | starts and exits, again and again | Logs of the previous run |

## Scenario A: pod Pending

### 1. Initial symptoms

- `oc get pods` shows a pod `Pending` for more than a minute.
- The control plane condition of that service stays `False` with
  "Deployment in progress".

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get pods --field-selector=status.phase=Pending
oc describe pod <pod> | sed -n '/^Events:/,$p'
oc get pvc
oc get pv
oc describe node | sed -n '/Allocated resources/,/Events/p'
oc get pod <pod> -o jsonpath='{.spec.nodeSelector}{"\n"}{.spec.affinity}{"\n"}'
```

### 3. Expected observations

The event text names the cause:

| Event message contains | Cause |
|------------------------|-------|
| `didn't find available persistent volumes to bind` | No free PersistentVolume: go to [Storage](storage.md) |
| `Insufficient memory` or `Insufficient cpu` | The sum of resource **requests** on the node is exhausted: go to [Resource exhaustion](resource-exhaustion.md) |
| `node(s) didn't match Pod's node affinity/selector` | A `nodeSelector` in the control plane resource matches no node |
| `node(s) had untolerated taint` | The node is cordoned or not ready: go to [Node and OKD](node-and-okd.md) |

No event at all for a StatefulSet pod that does not exist yet means the
previous ordinal is not ready: StatefulSets create pods in order.

The full event lines, as produced on the lab by throwaway pods asking for
too much memory, a node label that does not exist, and a volume larger than
any free one:

```text
Warning  FailedScheduling  0/1 nodes are available: 1 Insufficient memory. ...
Warning  FailedScheduling  0/1 nodes are available: 1 node(s) didn't match Pod's node affinity/selector. ...
Warning  FailedScheduling  0/1 nodes are available: 1 node(s) didn't find available persistent volumes to bind. ...
```

On the healthy lab the "Allocated resources" block shows memory requests
around 72 % and CPU requests around 31 % of the node. The OpenStack pods
have an empty `nodeSelector` and only a *preferred* anti-affinity, which
never blocks scheduling. A claim that waits for its pod shows
`WaitForFirstConsumer` in its events: that is normal, not a fault.

### 4. Root cause

`Pending` means the scheduler has not found a node that satisfies everything
the pod asks for (CPU and memory requests, volumes, selectors). Nothing has
started, so there is no log: the answer is always in the events.

### 5. Resolution

Follow the runbook named in the table. For a wrong `nodeSelector` (the lab
declares none, so this patch was only tried as a dry run, where it is
rejected with "The request is invalid" because there is nothing to remove):

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=json -p '[{"op":"remove","path":"/spec/nodeSelector"}]'
```

### 6. Verification

**[READ-ONLY]**

```bash
oc get pods -w
oc get openstackcontrolplane openstack
```

### 7. Risks and precautions

- Do not delete a Pending pod hoping it will schedule: the replacement has
  the same requirements.
- Do not delete a PVC to "unstick" a pod before reading
  [Storage](storage.md): the claim may be the only reference to existing
  data.

## Scenario B: CrashLoopBackOff after a configuration change

### 1. Initial symptoms

- After editing `customServiceConfig`, a pod shows `CrashLoopBackOff` or
  `Error` and its `RESTARTS` count climbs.
- Variant for the API services, which run behind Apache: the pod stays
  `Running` but never becomes ready (`0/2`), with `RESTARTS` at 0.
- The service resource stays `False` with "Deployment in progress".
- For a single-replica StatefulSet service (every Nova service, Glance) the
  service is down; for a Deployment (Keystone, Neutron, Placement) the old
  pod still serves.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get pods | grep -v 'Running\|Completed'
oc describe pod <pod> | sed -n '/Last State/,/Ready/p'
oc logs <pod> --previous --tail=50
oc logs <pod> --all-containers --tail=50
oc get events --sort-by=.lastTimestamp | grep -i back-off | tail -3

# What changed? Compare declared configuration with the repository template.
oc get oscp openstack -o jsonpath='{.spec.nova.template.schedulerServiceTemplate.customServiceConfig}{"\n"}'
oc get novascheduler nova-scheduler -o jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}'
oc diff -f .work/rendered/openstack/openstackcontrolplane.yaml
```

`--previous` is used without `--all-containers` on purpose: with several
containers, `oc logs --all-containers --previous` stops with an error as
soon as one of them has never restarted. Add `-c <container>` when the pod
has more than one (the `describe` output names the one that restarts).

### 3. Expected observations

- `Last State: Terminated`, `Reason: Error`, `Exit Code: 1`, and a restart
  every few seconds, then every few minutes (the back-off doubles up to five
  minutes). On the lab the counter went from 1 to 4 in 90 seconds.
- The previous log ends with the service's own error, an oslo.config message
  naming the option and the file:

  ```text
  oslo_config.cfg.ConfigFileValueError: Value for option max_attempts from LocationInfo(location=<Locations.user: (4, True)>, detail='/etc/nova/nova.conf.d/02-nova-override.conf') is not valid: invalid literal for int() with base 10: 'many'
  ```

- The events show `Back-off restarting failed container
  nova-scheduler-scheduler in pod nova-scheduler-0`.
- The operator is not in error. `NovaScheduler/nova-scheduler` reports
  `DeploymentReady False`, reason `Requested`, "Deployment in progress", and
  the control plane reports `OpenStackControlPlaneNovaReady False`, "Nova:
  Deployment in progress". From its point of view the operator did its job
  (the configuration was rendered and the workload updated); it is waiting
  for the pod to become ready, and it will wait forever.

The Apache variant looks different. With an unparsable boolean
(`debug = maybe`) in the Nova API configuration, observed on the lab:

- the pod `nova-api-0` stays `0/2 Running` with no restart; its events show
  readiness and startup probes failing with HTTP 500;
- the log is misleading: the WSGI application fails to load and reports
  `CantStartEngineError: No sql_connection parameter is established`, not
  the option you broke;
- the API route answers 503.

Not every wrong type is fatal: `osapi_compute_workers = many` in the same
place is not read by the Apache-hosted API and changes nothing.

### 4. Root cause

The operator writes `customServiceConfig` into the configuration file
without validating it. Unknown options are ignored by the service, but a
value of the wrong type (text where an integer is expected, an invalid
choice) makes the service exit at start-up. Kubernetes restarts the
container with an increasing delay: that is `CrashLoopBackOff`.

Other causes produce the same status with a different log:

- a dependency is unreachable at start-up (database, RabbitMQ): the log
  shows connection errors, go to [Galera and RabbitMQ](galera-and-rabbitmq.md);
- the container is killed for memory: `Reason: OOMKilled`, go to
  [Resource exhaustion](resource-exhaustion.md);
- a failing liveness probe: events show `Liveness probe failed` and the exit
  code is 137 or 143.

### 5. Resolution

Correct or remove the bad value at the source. The operator re-renders and
the pod starts cleanly on its next attempt.

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"nova":{"template":{"schedulerServiceTemplate":{"customServiceConfig":""}}}}}'
```

Measured on the lab: the scheduler pod is replaced and ready about 25
seconds after the revert, without waiting for the back-off.

If the pod is deep in back-off and you do not want to wait up to five
minutes:

**[CHANGE]**

```bash
oc delete pod <pod>
```

### 6. Verification

**[READ-ONLY]**

```bash
oc get pods -l service=nova-scheduler    # 1/1 Running, RESTARTS 0 on a new pod
oc get novascheduler nova-scheduler
oc get openstackcontrolplane openstack
oc rsh openstackclient openstack compute service list
```

### 7. Risks and precautions

- Read the previous log **before** deleting the pod; deletion discards it.
- Do not fix the generated Secret or the pod by hand: the operator restores
  the bad value from the control plane resource.
- Do not edit the liveness probe or the command of the workload to keep a
  broken service "up".

### Reproduce it in the lab

Give the Nova scheduler a value of the wrong type. `max_attempts` must be an
integer.

**[CHANGE]** Stops the scheduler until reverted: running instances are not
affected, new instances cannot be placed.

```bash
oc patch openstackcontrolplane openstack --type=merge -p '
spec:
  nova:
    template:
      schedulerServiceTemplate:
        customServiceConfig: |
          [scheduler]
          max_attempts = many
'
oc get pods -l service=nova-scheduler -w
```

`nova-scheduler-0` is in `CrashLoopBackOff` within a minute. Revert with the
command of section 5.

## Scenario C: ImagePullBackOff

### 1. Initial symptoms

- A new pod shows `ErrImagePull` then `ImagePullBackOff` and never starts.
- Typical trigger on OKD: enabling `telemetry`, whose pods use an image from
  a registry that requires a Red Hat account.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get pods | grep -i 'ImagePull\|ErrImage'
oc describe pod <pod> | sed -n '/^Events:/,$p'
oc get pod <pod> -o jsonpath='{range .spec.containers[*]}{.name}{"\t"}{.image}{"\n"}{end}'
oc get openstackversion openstack -o json | jq '.status.containerImages' | head -40
```

### 3. Expected observations

The event shows the image reference and the registry's answer:

| Event message contains | Cause |
|------------------------|-------|
| `unauthorized` or `authentication required` | The registry needs credentials the cluster does not have |
| `manifest unknown` or `not found` | The tag or digest does not exist (any more) |
| `i/o timeout`, `no such host`, `connection refused`, `pinging container registry` | The node cannot reach the registry: go to [DNS and routing](dns-and-routing.md) |

Observed on the lab with throwaway pods: an image from the subscription-only
registry fails with `unable to retrieve auth token: invalid username/password:
unauthorized`; a tag that does not exist fails with `manifest unknown`. When
the node reaches the Internet through an HTTP proxy, an unknown registry
host does not give `no such host` but `pinging container registry <host>:
... Internal Server Error`, because the answer comes from the proxy.

### 4. Root cause

The image of each service comes from the `OpenStackVersion` resource, which
lists one image per component. Most default images are public. A few are
not, and an OKD cluster installed with the placeholder pull secret has no
credentials for a subscription-only registry.

### 5. Resolution

Either do not run the service:

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '{"spec":{"telemetry":{"enabled":false}}}'
```

or point the component at an image you can pull, through
`spec.customContainerImages` of the `OpenStackVersion` resource. The field
name for each image is listed in its status:

**[READ-ONLY]**

```bash
oc explain openstackversion.spec.customContainerImages | head -60
```

### 6. Verification

**[READ-ONLY]**

```bash
oc get pods | grep -ci 'ImagePull' || true
oc get openstackcontrolplane openstack
```

### 7. Risks and precautions

- Deleting the pod does not help; the next one pulls the same image.
- Overriding an image pins it: it no longer follows operator updates. Record
  the override in the repository.
- Never add personal registry credentials to a lab you intend to share.
