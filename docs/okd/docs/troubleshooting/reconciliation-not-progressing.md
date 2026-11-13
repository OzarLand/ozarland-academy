# Reconciliation not progressing

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) for the investigation, the missing NetworkAttachmentDefinition (5b) and the operator restart (5d); the missing `osp-secret` key (5a) was not executed (a wrong value desynchronises a service from Keystone), and of the condition table only the `NetworkAttachmentsReady` and `DeploymentReady` rows were observed

## In short

- Nothing stops and nothing prints: the operator writes where it is
  blocked into the conditions of the resource.
- Read in this order: control plane conditions, then the service
  resource (and its children), then `observedGeneration`, then the
  operator log, then the inputs.
- The first condition that is not `True` names the blocked step; fix the
  earliest one, the others follow.
- Creating the missing input restarts the attempt by itself. Restarting
  the operator pod is the last step, and harmless for the service.
- Never delete a service resource to force a retry.

You declared a state and the platform does not reach it: the control plane
or a service resource stays `False`. With Kolla-Ansible a failed deploy
stops with an Ansible error on your terminal. Here nothing stops and nothing
prints: the operator keeps retrying and writes where it is blocked into the
conditions. The work is to read them in the right order.

## 1. Initial symptoms

- `oc get openstackcontrolplane` shows `STATUS=False` (or `Unknown`) for more
  than ten minutes.
- A change you applied has no visible effect.
- A new service resource exists but no pod appears.

## 2. Read-only investigation

### Step 1: which service?

**[READ-ONLY]**

```bash
oc get oscp openstack -o json | jq -r '.status.conditions[] | select(.status != "True") | "\(.type)\t\(.reason)\t\(.message)"'
```

### Step 2: which step of that service?

Go to the resource the condition mirrors, and one level further if that
resource has children (Nova and Glance do).

**[READ-ONLY]**

```bash
oc get keystoneapi,placementapi,glance,glanceapi,neutronapi,nova,novaapi,novascheduler,novaconductor,novametadata,novacell,galera,memcached,dnsmasq,ovndbcluster,ovnnorthd,ovncontroller
oc get <kind> <name> -o json | jq -r '.status.conditions[] | select(.status != "True") | "\(.type)\t\(.reason)\t\(.message)"'
```

On the lab the first command lists every kind except `ovncontroller` (no
such resource exists: the OVN controller of this lab runs on the compute
node, deployed by the data plane). `nova` and `novacell` print only NAME and
AGE; read their conditions with the second command.

### Step 3: is the generation observed?

**[READ-ONLY]**

```bash
oc get <kind> <name> -o jsonpath='generation={.metadata.generation} observed={.status.observedGeneration}{"\n"}'
```

### Step 4: what does the operator say?

**[READ-ONLY]**

```bash
oc -n openstack-operators get pods
oc -n openstack-operators logs deployment/<service>-operator-controller-manager --since=15m | grep -i 'error\|<name>' | tail -40
oc get events --sort-by=.lastTimestamp | tail -30
```

### Step 5: are the inputs there?

**[READ-ONLY]**

```bash
oc get secret osp-secret -o json | jq -r '.data | keys[]'
oc get network-attachment-definitions
oc get storageclass
oc get pvc
oc get issuers,certificates
oc get jobs
```

## 3. Expected observations

The first condition that is not `True`, read in the order the operator works,
tells you the blocked step:

| Condition (service resource) | Message | Meaning and next step |
|------------------------------|---------|-----------------------|
| `InputReady` | `Input data resources missing` | A Secret or a key in it is absent. The operator log says `field <Key> not found in Secret osp-secret`. Section 5a. |
| `NetworkAttachmentsReady` | `NetworkAttachment resources missing: <name>` (reason `Error`) | The NetworkAttachmentDefinition named in `networkAttachments` does not exist. Section 5b. |
| `NetworkAttachmentsReady` | `NetworkAttachments error occurred not all pods have interfaces with ips as configured in NetworkAttachments: [<name>]` | Transient while a pod with a secondary interface starts; a fault only if it lasts. |
| `TLSInputReady` | `TLSInput is missing: <secret>` | A certificate Secret has not been issued: check cert-manager and `oc get certificates`. |
| `DBReady` | `DB create job still running` or an error | The database server is not ready: see [Galera and RabbitMQ](galera-and-rabbitmq.md). |
| `RabbitMqTransportURLReady` | waiting | RabbitMQ is not ready: same runbook. |
| `DBSyncReady`, `BootstrapReady` | job running or error | Read the Job log: `oc logs job/<service>-db-sync`. |
| `DeploymentReady` | `Deployment in progress` | The workload exists but its pods are not ready: see [Pod Pending or CrashLoopBackOff](pod-pending-or-crashloop.md). |
| `ExposeServiceReady` | in progress or error | A Service of type LoadBalancer has no address, or a Route is rejected: see [Network](network.md). |
| `KeystoneServiceReady`, `KeystoneEndpointReady` | waiting | Keystone itself is not ready; fix Keystone first. |

Other signs:

- `observedGeneration` lower than `generation`: the operator has not
  processed your last edit. Either it is busy, or its pod is not running.
- An operator pod in `CrashLoopBackOff`: nothing of that service will be
  reconciled until it runs.
- Conditions with status `Unknown` and reason `Init` are simply not reached
  yet: the blocker is earlier in the list.
- On the control plane resource, a wrong `storageClass` shows up indirectly:
  `...MariaDBReady` and `...RabbitMQReady` stay `False` and PVCs are
  `Pending` (see [Storage](storage.md)).

## 4. Root cause

A reconciliation is a function that runs from the top each time: check
inputs, render configuration, create the database, run db-sync, create the
workload, expose it, register it in Keystone. When a step cannot complete,
the operator sets the matching condition to `False`, and either:

- **requeues**: asks to be called again after a delay (seconds). This is the
  "waiting" case, reason `Requested`. It resolves itself as soon as the
  missing input appears, with no action on the service.
- **returns an error**: reason `Error`. The controller retries with an
  increasing delay. It also resolves itself when the cause is fixed, but may
  take a minute or two to notice.

Operators also watch the objects they depend on, so creating the missing
Secret or NetworkAttachmentDefinition triggers a new attempt immediately.
You almost never need to "kick" an operator.

The dependency order explains cascades: Galera, RabbitMQ and memcached come
first, then Keystone, then everything else. One missing input at the bottom
makes many conditions `False`; always fix the earliest one.

## 5. Resolution

### 5a. A key is missing from `osp-secret`

**[CHANGE]**

```bash
oc patch secret osp-secret --type=merge -p "{\"stringData\":{\"PlacementPassword\":\"$(openssl rand -hex 16)\"}}"
```

Use this only for a key that never existed (a service being enabled for the
first time). If the key existed and was removed, restore the **same** value:
the Keystone user and the database account were created with it.

### 5b. A NetworkAttachmentDefinition is missing

Re-apply the networks from the repository (idempotent):

**[CHANGE]**

```bash
scripts/bastion/06-openstack-controlplane.sh
```

or only the rendered manifest:

**[CHANGE]**

```bash
oc apply -f .work/rendered/openstack/networks.yaml
```

### 5c. The operator pod is not running

**[READ-ONLY]**

```bash
oc -n openstack-operators describe pod <operator-pod> | sed -n '/^Events:/,$p'
oc -n openstack-operators logs <operator-pod> --previous --tail=50
```

An operator pod that crashes with webhook certificate errors points at
cert-manager; one that is `OOMKilled` needs more memory (the `OpenStack`
initialization resource has `operatorOverrides` for this).

### 5d. Nothing is wrong, but nothing moves

As a last step, restart the operator pod. This is harmless for the service.

**[CHANGE]**

```bash
oc -n openstack-operators delete pod -l openstack.org/operator-name=<service>
oc -n openstack-operators get pods -w
```

Every operator pod carries the label `openstack.org/operator-name` with
the short service name (`keystone`, `nova`, `neutron`, `mariadb`, `infra`,
`rabbitmq-cluster`, ...). Measured on the lab with the neutron operator: the
new pod is `Running` in less than 20 seconds.

## 6. Verification

**[READ-ONLY]**

```bash
oc get <kind> <name>                     # STATUS True
oc get openstackcontrolplane openstack   # STATUS True
oc get oscp openstack -o json | jq -r '[.status.conditions[] | select(.status != "True")] | length'
```

## 7. Risks and precautions

- Do not delete the service resource (`oc delete keystoneapi keystone`) to
  force a retry: the openstack operator recreates it, but the deletion runs
  the service's clean-up logic first, which can remove its database and
  Keystone registration.
- Do not delete the `OpenStackControlPlane` to start over unless you intend
  to rebuild: it owns everything.
- Resist changing several things while waiting. Reconciliation is
  asynchronous; give one fix two minutes before judging it.
- Scaling an operator to zero stops reconciliation for its service. Useful
  for an emergency manual intervention, dangerous to forget.

## Reproduce it in the lab

Remove a NetworkAttachmentDefinition that Neutron needs, then make Neutron
start a new pod so that the definition is needed again.

**[CHANGE]** Neutron API keeps running on its existing pod as long as you
do not delete it.

```bash
oc get network-attachment-definitions internalapi -o yaml > /tmp/nad-internalapi.yaml
oc delete network-attachment-definitions internalapi
oc get neutronapi neutron -o json | jq -r '.status.conditions[] | select(.status != "True")'
```

Observed on the lab: nothing happens. Two minutes after the deletion every
condition is still `True` and the Neutron API still answers. A
NetworkAttachmentDefinition is only read when a pod is created, and deleting
one does not trigger a reconciliation of the services that name it. This is
a fault that stays hidden until the next restart.

**[CHANGE]** Takes the Neutron API down until the definition is restored.

```bash
oc delete pod -l service=neutron
oc get pods -l service=neutron
oc get events --sort-by=.lastTimestamp | grep -i 'network-attachment' | tail -3
oc get neutronapi neutron -o json | jq -r '.status.conditions[] | select(.status != "True") | "\(.type)\t\(.reason)\t\(.message)"'
```

The new pod stays in `ContainerCreating`. Its events say why:

```text
Warning  NoNetworkFound          pod/neutron-...  cannot find a network-attachment-definition (internalapi) in namespace (openstack): network-attachment-definitions.k8s.cni.cncf.io "internalapi" not found
Warning  FailedCreatePodSandBox  pod/neutron-...  Failed to create pod sandbox: ...
```

and the operator now reports it:

```text
NetworkAttachmentsReady  Error  NetworkAttachment resources missing: internalapi
```

Restore:

**[CHANGE]**

```bash
oc apply -f .work/rendered/openstack/networks.yaml
```

The pod starts without further action. `NetworkAttachmentsReady` passes
through "not all pods have interfaces with ips as configured" and the
control plane is `True` again about 45 seconds after the `oc apply`.
