---
title: "Safe change checklist"
description: "Operators make changes easy to apply. They do not make them safe: a wrong value is rolled out as diligently as a right one."
---

# Safe change checklist

> Status: validated on the lab (OKD 4.22.0-okd-scos.10, operators 18-stable) on 2026-11-11

Operators make changes easy to apply. They do not make them safe: a wrong
value is rolled out as diligently as a right one. This checklist is the
discipline to keep around every change to the control plane resource, the
NodeSet, or anything in the `openstack` namespace.

## In short

- Before: the platform is healthy, the starting point is saved, and the
  change was previewed with `--dry-run=server`.
- During: one change at a time, on the highest-level resource, watched in
  a second terminal, with a stop condition decided in advance.
- After: the control plane is `True`, only the expected pods were
  replaced, and the smoke test passes.
- Rolling back is applying the previous declaration. It does not undo
  schema migrations, written data, or what was applied on compute nodes.

## 1. Initial symptoms

You are about to apply a change, or you applied one and are not sure the
platform has settled.

## 2. Read-only investigation

Before changing anything, establish that the platform is healthy and record
the starting point. A change applied on top of an existing fault produces
two faults that look like one.

**[READ-ONLY]**

```bash
# Platform healthy?
oc get nodes
oc get clusteroperators | awk 'NR==1 || $3!="True" || $5!="False"'
oc adm top node

# OpenStack healthy?
oc get openstackcontrolplane openstack
oc get pods --field-selector=status.phase!=Running,status.phase!=Succeeded
tests/smoke-test.sh

# Starting point, for diff and rollback.
mkdir -p ~/changes
oc get openstackcontrolplane openstack -o yaml > ~/changes/oscp-$(date -u +%Y%m%dT%H%M%S).yaml
oc get pods --no-headers -o custom-columns=NAME:.metadata.name,STARTED:.status.startTime | sort > ~/changes/pods-before.txt
```

The commands keep you in the repository directory, where
`tests/smoke-test.sh` lives. The pod list records names and start times
only: a plain `oc get pods` listing contains an AGE column that differs on
every call and makes a later `diff` useless.

Preview what the API server would store, without storing it:

**[READ-ONLY]**

```bash
oc patch openstackcontrolplane openstack --type=merge --dry-run=server -o yaml -p '<your patch>' | diff -u <(oc get oscp openstack -o yaml) - | less
```

## 3. Expected observations

- The node is `Ready`; the cluster operator filter prints only its header
  line (every operator available and not degraded); memory usage leaves
  headroom for one extra pod during a rollout (about 70 % used on the idle
  lab).
- The control plane is `True`, the pod filter answers `No resources found in
  openstack namespace.` and the smoke test ends with `0 check(s) failed`.
- The dry-run diff shows your change, plus `generation` increased by one,
  and nothing else:

  ```text
  -  generation: 17
  +  generation: 18
  ...
  -      replicas: 1
  +      replicas: 2
  ```

- A rejected dry run means the API schema or an admission webhook of the
  operator refuses the change. The message names the field. Two real
  examples from the lab, a wrong type and a forbidden value:

  ```text
  admission webhook "mopenstackcontrolplane-v1beta1.kb.io" denied the request: json: cannot unmarshal string into Go struct field KeystoneAPISpecCore.spec.keystone.template.replicas of type int32
  The OpenStackControlPlane "openstack" is invalid: spec.rabbitmq.template[rabbitmq].replicas: Forbidden: scaling down from 1 to 0 replicas is not supported; ...
  ```

## 4. Root cause

Why a checklist is still needed with operators:

- The operator validates structure (through webhooks), not intent. It cannot
  know that `debug = ture` is a typo: the content of `customServiceConfig`
  is accepted whatever it says, and the service finds out at start-up.
- Reconciliation is asynchronous. `oc patch` returning success means "stored",
  not "applied". The result arrives seconds to minutes later, in conditions.
- A single field can fan out: changing a top-level setting such as TLS or the
  storage class touches every service.
- There is no transaction and no automatic rollback. If step 3 of 5 fails,
  steps 1 and 2 stay applied.

## 5. Resolution

Apply the change with these rules:

1. **One change at a time.** One service, one field. Wait for `True` before
   the next.
2. **Change the highest-level resource** (`OpenStackControlPlane`,
   `OpenStackDataPlaneNodeSet`), never a generated object.
3. **Use `oc patch` or `oc apply` with a file you keep**, rather than an
   interactive edit, so the change can be reviewed and repeated.
4. **Watch while it rolls**, in a second terminal:

   **[READ-ONLY]**

   ```bash
   oc get openstackcontrolplane openstack -w
   oc get pods -w
   ```

5. **Decide in advance when to stop.** Roll back if any of these holds:
   - a new pod is in `CrashLoopBackOff`, `Error` or `ImagePullBackOff`;
   - a condition shows reason `Error`;
   - a condition stays `False` with reason `Requested` for more than ten
     minutes without the message changing;
   - an unrelated service becomes unhealthy.

### Roll back

Rolling back is applying the previous declaration. For a single field:

**[CHANGE]**

```bash
oc patch openstackcontrolplane openstack --type=merge -p '<patch with the previous value>'
```

For anything larger, re-apply the repository template, which is the known
good state of the lab:

**[CHANGE]** Reverts every manual change to the control plane resource.

```bash
scripts/bastion/06-openstack-controlplane.sh
```

A saved `oc get -o yaml` export contains `status`, `resourceVersion` and
other server-side fields. Use it as a reference for `diff`, not as a file to
`oc apply` blindly.

What a rollback does **not** undo:

- Database schema migrations run by a db-sync Job.
- Data written or deleted by the service while the change was active.
- Anything applied on compute nodes: that needs a new data plane deployment
  with the previous values.
- Deleted PersistentVolumeClaims or Secrets.

## 6. Verification

**[READ-ONLY]**

```bash
oc get openstackcontrolplane openstack
oc get pods --field-selector=status.phase!=Running,status.phase!=Succeeded
oc get pods --no-headers -o custom-columns=NAME:.metadata.name,STARTED:.status.startTime | sort | diff ~/changes/pods-before.txt - || true
tests/smoke-test.sh
```

The `diff` must list only the pods you expected to be replaced. Be aware
that a change can restart more than its own service: on the lab, enabling
Horizon also rolled the Glance pod.

For a change that can affect instances, also run the functional test, which
boots and deletes a test instance:

**[CHANGE]** Creates and deletes OpenStack resources.

```bash
tests/smoke-test.sh --functional
```

Finally, record the change in the repository template if it is meant to
last.

## 7. Risks and precautions

- Most changes restart a service. On a single-replica lab every change is a
  short outage of that service; say so before you start.
- Stateful services (Galera, RabbitMQ, OVN databases) deserve a stricter
  rule: no change without a reason, never two at once, and never while
  another change is still rolling.
- Do not combine an OpenStack change with OKD maintenance (node reboot,
  cluster upgrade). See [node and OKD](../troubleshooting/node-and-okd.md)
  and
  [impact of OKD maintenance on OpenStack](../lifecycle/06-okd-maintenance-impact.md).
- Stop and investigate rather than stacking a second change on a failing
  first one. Use
  [reconciliation not progressing](../troubleshooting/reconciliation-not-progressing.md).
- If in doubt on a lab: take notes, then try. If in doubt in production:
  do not.

---

**Previous:** [Data plane changes](08-dataplane-changes.md) · **Up:** [Operations guide](index.md) · **Next:** [Lifecycle management](../lifecycle/index.md)
