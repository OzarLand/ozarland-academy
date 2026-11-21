# Manual changes reverted, deleted objects coming back

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

## In short

- Only the `OpenStackControlPlane` (and the other top resources) is
  yours. Everything with an `ownerReferences` entry is rebuilt from
  above.
- An edit of a managed field is reverted within a second; an edit of a
  field the operator does not set survives as invisible drift.
- Changes made inside OpenStack (an endpoint URL) are not noticed until
  the owning resource is reconciled again.
- Deleted pods, Deployments and generated Secrets come back. A deleted
  claim does not come back with its data.
- To stop an operator in an emergency, use `operatorOverrides`; scaling
  its Deployment by hand is itself reverted.

Sooner or later an operator from the Kolla world edits a Deployment or a
ConfigMap directly, as one would hot-fix a file under `/etc/kolla/`. The
edit vanishes, or seems to stick and disappears days later. This runbook
explains what the operators do with objects they manage and why a manual
change is at best useless and at worst a time bomb.

## 1. Initial symptoms

- You ran `oc edit deployment keystone` (or `oc scale`, or edited a generated
  Secret) and the object is back to its previous content within seconds.
- You deleted a pod, a Deployment or a Secret and it reappeared.
- A manual fix "worked" until an unrelated change, an operator restart or an
  upgrade removed it.
- A setting changed with the OpenStack CLI (an endpoint URL) reverted.

## 2. Read-only investigation

Who owns the object, and who last wrote which field?

**[READ-ONLY]**

```bash
# Ownership chain.
oc get deployment keystone -o jsonpath='{range .metadata.ownerReferences[*]}{.apiVersion} {.kind}/{.name} controller={.controller}{"\n"}{end}'
oc get keystoneapi keystone -o jsonpath='{range .metadata.ownerReferences[*]}{.apiVersion} {.kind}/{.name}{"\n"}{end}'

# Field-level authorship: which client set what, and when.
oc get deployment keystone -o yaml --show-managed-fields | sed -n '/managedFields:/,/^spec:/p' | grep -E 'manager:|operation:|time:'

# What the operator did about it.
oc -n openstack-operators logs deployment/keystone-operator-controller-manager --since=10m | tail -20
oc get events --sort-by=.lastTimestamp | tail -20

# Declared value versus live value.
oc get oscp openstack -o jsonpath='{.spec.keystone.template.replicas}{"\n"}'
oc get keystoneapi keystone -o jsonpath='{.spec.replicas}{"\n"}'
oc get deployment keystone -o jsonpath='{.spec.replicas}{"\n"}'
```

## 3. Expected observations

- The chain reads Pod, ReplicaSet, `Deployment/keystone`,
  `KeystoneAPI/keystone`, `OpenStackControlPlane/openstack`. Only the last
  one has no owner: it is the only object that is yours.
- `managedFields` lists the operator under the name `manager`, with a
  timestamp that moves to the second of your edit: that is the revert.
  `kube-controller-manager` (which writes the status) is always there too.
  An edit to a field the operator does not own leaves its own entry, for
  example `kubectl-annotate`.
- The three replica values are equal (`1`): the lower levels were rewritten
  from the top.
- The operator log is of little help here: reverting a drift is ordinary
  reconciliation and is not logged as an event of its own. The namespace
  events tell the story better, for example after a manual scale:

  ```text
  Normal  ScalingReplicaSet  deployment/keystone  Scaled up replica set keystone-7b45c49ccb from 1 to 2
  Normal  ScalingReplicaSet  deployment/keystone  Scaled down replica set keystone-7b45c49ccb from 2 to 1
  ```

## 4. Root cause

Each operator rebuilds the objects it owns from the resource above them, on
every reconciliation. A reconciliation runs when the owner changes, when the
owned object changes (operators watch what they create), when a dependency
changes, and when the operator restarts. No periodic pass was seen on the
lab: over 11 hours, idle operators logged nothing (see
[when operators reconcile](../knowledge-base/okd-olm-and-operators.md#how-do-i-read-an-operators-logs-and-when-do-operators-actually-reconcile)).
What happens to your manual change depends on the kind of object:

| You change... | What happens |
|---------------|--------------|
| A field of a Deployment or StatefulSet that the operator sets (`replicas`, image, env, volumes, pod template annotations) | Reverted in under a second, because the edit itself triggers a reconciliation. Measured on the lab: `oc scale deployment keystone --replicas=2` was back to 1 before the next poll; the extra pod was created and deleted in the same second. |
| The pod template through `oc rollout restart` | Same revert. On a Deployment the new pod is removed before it is ready and nothing restarts; on a StatefulSet the pod restarts once. |
| A field the operator does not set (an annotation on the Deployment itself) | Survives, including across later reconciliations. Invisible drift. |
| A generated configuration Secret (`keystone-config-data`) | Re-rendered within a second. The pod is not restarted and never sees your content. |
| A service resource (`KeystoneAPI/keystone`) | Overwritten by the openstack operator from the `OpenStackControlPlane` within about three seconds. |
| A Service or Route created for an endpoint | Recreated or patched back, including MetalLB annotations. |
| Something inside OpenStack that an operator registers (a Keystone endpoint URL changed with `openstack endpoint set`) | **Not** noticed: the operator does not watch the Keystone database. On the lab the wrong URL stayed for several minutes and was only corrected when the keystone operator reconciled the `KeystoneEndpoint` resource again (here: after a restart of the operator pod). |

And for deletions:

| You delete... | What happens |
|---------------|--------------|
| A pod | Its ReplicaSet, StatefulSet or DaemonSet starts a new one immediately. This is the normal way to restart. |
| A Deployment or StatefulSet | The service operator recreates it immediately; its pods are replaced (outage). Measured with the Placement Deployment: recreated in the same second, new pod ready after 24 s. PVCs of a StatefulSet are kept. |
| A generated Secret or ConfigMap | Recreated by the operator within a second. A pod that starts in the gap fails to mount it and waits. |
| A Job (`keystone-db-sync`) | Nothing to delete on a healthy lab: completed Jobs are already removed by the operator. It is run again only when its inputs change. |
| A service resource (`KeystoneAPI`) | Recreated by the openstack operator, **after** the service operator's clean-up has run. May remove the service's database and Keystone registration. |
| A PVC | **Not** recreated with its data. A new empty claim is created for a StatefulSet; with `Retain` volumes the old data stays on disk but nothing points to it (see [Storage](storage.md)). |
| `osp-secret` | Not recreated: it is an input you own. Services report `InputReady=False`. |
| The `OpenStackControlPlane` | Everything it owns is garbage-collected. This is an uninstall. |

Why it is dangerous and not just ineffective:

- **False confidence.** A hot-fix that survives for a while looks like a fix.
  It is removed by the next unrelated change, at the worst moment, with no
  record of what it was.
- **Double rollouts.** Edit plus revert restarts the service twice.
- **Diverging truth.** The repository, the control plane resource and the
  running system no longer agree; the next person debugs a system that
  matches no description.
- **Fighting the controller.** Repeating the edit (or scripting it) makes
  the operator and you overwrite each other in a loop.

## 5. Resolution

Make the change where it is declared:

| You wanted to change | Declare it in |
|----------------------|---------------|
| A configuration option | `customServiceConfig` of the service in the `OpenStackControlPlane` ([guide](../operations/04-change-service-configuration.md)) |
| Replica count | `replicas` of the service template ([guide](../operations/06-scale-a-service.md)) |
| Container image | `OpenStackVersion` `spec.customContainerImages` |
| Service exposure, load balancer IP | `override.service` of the service template |
| Resources of an operator pod | `operatorOverrides` in the `OpenStack` initialization resource |
| Anything on a compute node | The NodeSet, then a new deployment ([guide](../operations/08-dataplane-changes.md)) |

If a manual change was made and you are unsure what remains, re-apply the
repository state and compare:

**[READ-ONLY]**

```bash
oc diff -f .work/rendered/openstack/openstackcontrolplane.yaml
```

**[CHANGE]**

```bash
oc apply -f .work/rendered/openstack/openstackcontrolplane.yaml
```

### Emergency: you really must change a managed object

It is possible to stop an operator so that it no longer reverts you. This is
an emergency measure with a clear end.

Scaling the operator Deployment by hand does **not** work: the operator
Deployments are themselves managed, by the `OpenStack` initialization
resource in the `openstack-operators` namespace. On the lab,
`oc scale deployment/keystone-operator-controller-manager --replicas=0` was
back to 1 after four seconds, and the same happened with
`openstack-operator-controller-manager` after two seconds. The rule of this
page applies one level up: declare it in the owner.

**[CHANGE]** Stops all reconciliation for that service (effective within
three seconds).

```bash
oc -n openstack-operators patch openstack openstack --type=merge -p '{"spec":{"operatorOverrides":[{"name":"keystone","replicas":0}]}}'
oc -n openstack-operators get deployment keystone-operator-controller-manager
```

With the keystone operator stopped, a manual `oc scale deployment keystone
--replicas=2` sticks, and both `KeystoneAPI/keystone` and the control plane
resource keep reporting `True`: nothing shows the drift.

Write down what you changed, and undo both the change and the override as
soon as the incident is over.

**[CHANGE]** Starts the operator again. It reconciles at once and reverts
every manual change it finds (the Deployment was back to one replica 25
seconds after the operator pod was ready).

```bash
oc -n openstack-operators patch openstack openstack --type=json -p '[{"op":"remove","path":"/spec/operatorOverrides"}]'
```

The `remove` patch assumes no other operator override is declared; the lab
has none by default.

## 6. Verification

**[READ-ONLY]**

```bash
oc get oscp openstack -o jsonpath='{.spec.keystone.template.replicas}{"\n"}'
oc get deployment keystone -o jsonpath='{.spec.replicas}{"\n"}'
oc get openstackcontrolplane openstack
oc -n openstack-operators get deployments          # every operator at 1/1
oc -n openstack-operators get openstack openstack  # True, 21 operators deployed
```

## 7. Risks and precautions

- Treat every object with an `ownerReferences` entry as read-only.
- `oc edit` on a managed object can restart a service twice. On Galera or
  RabbitMQ that is two outages of everything.
- Never delete a PVC, `osp-secret`, a service resource or the control plane
  resource as an experiment on a lab you want to keep.
- An operator left at zero replicas silently stops certificate renewal
  handling, configuration updates and recovery for its service, and no
  condition reports it.
- `oc diff -f .work/rendered/openstack/openstackcontrolplane.yaml` prints
  nothing and returns 0 when the declared state is the repository state. It
  only compares the control plane resource, not the objects below it.

## Reproduce it in the lab

Three safe experiments, each observable in under a minute.

**[CHANGE]** Scale a managed Deployment by hand and watch it come back. The
revert is faster than the watch: look at the events to see that anything
happened.

```bash
oc scale deployment keystone --replicas=2
oc get deployment keystone
oc get events --sort-by=.lastTimestamp | grep deployment/keystone | tail -2
```

**[CHANGE]** Delete a managed pod and watch its replacement.

```bash
oc delete pod -l service=placement
oc get pods -l service=placement -w
```

**[CHANGE]** Edit a generated Secret and watch it be re-rendered. The pod is
not restarted by this, so the service is unaffected.

```bash
oc get secret keystone-config-data -o jsonpath='{.data.custom\.conf}' | base64 -d
oc patch secret keystone-config-data --type=merge -p '{"stringData":{"custom.conf":"[DEFAULT]\ndebug = true\n"}}'
sleep 5
oc get secret keystone-config-data -o jsonpath='{.data.custom\.conf}' | base64 -d
```

Observed on the lab: all three are undone at once. The Deployment is back
to one replica and the Secret back to its empty `custom.conf` within a
second; the new Placement pod is ready after about 25 seconds.
