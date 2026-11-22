---
title: "Investigating a failed or stalled upgrade"
description: "Read-only, top-down method to find the first non-ready link of a failed or stalled OpenStack upgrade, with stall causes and fixes that resume reconciliation."
---

# Investigating a failed or stalled upgrade

> Status: partially validated on the lab — every read-only command was run on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable), at rest and during a staged minor update, and the webhook refusals were checked with `--dry-run=server`; no update was deliberately broken, so the failure rows of section 3 and the resolutions of section 5 were not exercised

## In short

- There is no global "upgrade failed" flag. Find the first link of the
  chain that is not `Ready`, then debug it as outside an upgrade.
- Work top-down: which axis is moving, which stage, which service, which
  pod or job.
- The only "stall" seen on the lab is not a failure: the update waits for
  your data plane deployment at stages 2 and 8.
- Fix the cause; reconciliation resumes by itself. Do not set
  `targetVersion` back, edit workloads by hand or delete PVCs to unblock.
- The failure cases of this page come from the operator source: none was
  provoked on the lab.

## 1. Initial symptoms

One of:

- `oc wait openstackversion ... --for=condition=MinorUpdate...` times out.
- `OpenStackVersion` shows target different from deployed for a long time.
- The control plane stays not `Ready` after an operator upgrade.
- A new CSV stays in `Pending`, `Installing` or `Failed`.
- A data plane update deployment is not `Ready`.

There is no global "upgrade failed" flag. An update is a chain of ordinary
reconciliations; a failure is one link that never reaches `Ready`. The
method is always the same: find the first link that is not ready, then debug
it as you would outside an upgrade.

## 2. Read-only investigation

Work top-down. All commands are **[READ-ONLY]**.

Which axis is in motion?

```bash
oc -n openstack-operators get csv,subscription,installplan
oc -n openstack get openstackversion openstack \
  -o custom-columns=TARGET:.spec.targetVersion,AVAILABLE:.status.availableVersion,DEPLOYED:.status.deployedVersion
```

Operator upgrade stuck (CSV not `Succeeded`):

**[READ-ONLY]**

```bash
oc -n openstack-operators get csv -o json \
  | jq -r '.items[] | "\(.metadata.name)\t\(.status.phase)\t\(.status.reason)\t\(.status.message)"'
oc -n openstack-operators get pods
oc -n openstack-operators get events --sort-by=.lastTimestamp | tail -20
oc -n openstack-operators get openstack openstack -o json \
  | jq -r '.status.conditions[] | select(.status != "True") | "\(.type)\t\(.reason)\t\(.message)"'
```

Service update stuck — which stage:

**[READ-ONLY]**

```bash
oc -n openstack get openstackversion openstack -o json \
  | jq -r '.status.conditions[] | "\(.type)\t\(.status)\t\(.reason)\t\(.message)"' | column -t -s $'\t'
```

Then which service inside that stage:

**[READ-ONLY]**

```bash
oc -n openstack get openstackcontrolplane openstack -o json \
  | jq -r '.status.conditions[] | select(.status != "True") | "\(.type)\t\(.reason)\t\(.message)"'
oc -n openstack get pods --field-selector=status.phase!=Running,status.phase!=Succeeded
oc -n openstack get pods -o wide | grep -Ev 'Running|Completed'
oc -n openstack get events --sort-by=.lastTimestamp | tail -30
```

For the suspect pod or job:

**[READ-ONLY]**

```bash
oc -n openstack describe pod <pod>
oc -n openstack logs <pod> --all-containers --tail=100
oc -n openstack logs <pod> --previous --tail=100
oc -n openstack get jobs
```

Data plane stage:

**[READ-ONLY]**

```bash
oc -n openstack get openstackdataplanedeployment
oc -n openstack get openstackdataplanedeployment <name> -o json \
  | jq -r '.status.conditions[] | select(.status != "True") | "\(.type)\t\(.reason)\t\(.message)"'
oc -n openstack get pods -l app=openstackansibleee --sort-by=.status.startTime
oc -n openstack logs <failed-ansible-pod> --tail=80
```

Operator view (what the controller itself complains about):

**[READ-ONLY]**

```bash
oc -n openstack-operators get deployments | grep openstack-operator
oc -n openstack-operators logs deployment/<openstack-operator-deployment> --tail=100 | grep -iE 'error|waiting'
```

The first command lists the Deployments of the openstack-operator itself:
`openstack-operator-controller-init` (the initialization controller, the
only one installed by the CSV) and `openstack-operator-controller-manager`
(the main controller); use the controller manager in the second.

At rest, every `select(.status != "True")` filter above prints nothing, the
CSV line reads `Succeeded  InstallSucceeded  install strategy completed with
no errors`, and the `OpenStack` resource has the conditions `Ready`,
`OpenStackOperatorDeploymentsReadyCondition` and
`OpenStackOperatorReadyCondition`.

## 3. Expected observations

The first six rows were observed on the lab during a healthy update; the
others come from the operator source and were not provoked.

What a healthy update looks like while it waits for you (real output):

```text
Ready                       False    Requested  in progress
Initialized                 True     Ready      completed
MinorUpdateControlplane     Unknown  Init       not started
MinorUpdateDataplane        Unknown  Init       not started
MinorUpdateKeystone         Unknown  Init       not started
MinorUpdateMariaDB          Unknown  Init       not started
MinorUpdateMemcached        Unknown  Init       not started
MinorUpdateOVNControlplane  True     Ready      completed
MinorUpdateOVNDataplane     False    Requested  in progress
MinorUpdateRabbitMQ         Unknown  Init       not started
```

| Observation | Meaning |
|---|---|
| `MinorUpdateOVNControlplane` True, `MinorUpdateOVNDataplane` False, reason `Requested`, message "in progress" | Not a failure: the operator is waiting for *your* OVN data plane deployment |
| `MinorUpdateControlplane` True, `MinorUpdateDataplane` False, "in progress" | Not a failure: waiting for your `update` data plane deployment |
| Stages `Unknown`, reason `Init`, message "not started" | Not a failure: stages not reached yet. The conditions of already finished stages are also reset to this for a few seconds between the Keystone stage and the rest of the control plane |
| `OpenStackControlPlane` not `Ready` during the update, service conditions `False` one after another | Normal: each service reports its own rollout |
| No `MinorUpdate*` condition at all, the three versions equal | The update is finished: the stage conditions are removed at the end |
| `MinorUpdateAvailable` True while target equals deployed | The installed operator knows another version than the deployed one — newer after an operator upgrade, but also *older* if the operator content was put back |
| A stage condition False for a long time and a pod in `ImagePullBackOff` / `ErrImagePull` | The target image cannot be pulled (wrong `customContainerImages`, registry unreachable, registry needing credentials) |
| A `*-db-sync` Job failing, service condition `DBSyncReady` False | Schema migration failed; read the Job pod log |
| Galera or RabbitMQ pod not ready during `MinorUpdateMariaDB` / `MinorUpdateRabbitMQ` | Stateful restart problem; see [troubleshooting](../troubleshooting/galera-and-rabbitmq.md) |
| `MinorUpdateControlplane` False with an error message | The control plane reported an error after the images were applied; read the control plane conditions |
| CSV `Pending`, reason mentioning requirements | Missing prerequisite: Kubernetes version, a CRD, or an unapproved InstallPlan |
| CSV `Installing` forever, an operator pod crash-looping | The new operator cannot start: read its log; a classic cause is a missing webhook certificate (cert-manager not healthy) |
| Data plane deployment False, an Ansible pod in `Error` | A task failed on a node; the pod log ends with the Ansible error |
| `patch` of `targetVersion` rejected by the webhook with "must be in the list of current or previous available versions" | Target not in the known versions (observed). A second refusal exists when `customContainerImages` is set and left unchanged across a version change ([01](01-openstack-version-and-minor-update.md)) |

## 4. Root cause explanation

The typical causes, from most to least frequent in a lab:

1. **Waiting, not failing.** Two of the eight stages need a data plane
   deployment that only the administrator creates. This is the only
   "stall" seen on the lab.
2. **Image pull failures.** The operators default to images referenced by
   digest; overrides and the "fake update" helper use tags. On OKD, any
   image hosted on a registry that requires a Red Hat account cannot be
   pulled.
3. **A service that was already unhealthy before the update.** The update
   only surfaces it because every pod is restarted. This is why the
   pre-checks matter.
4. **Resource exhaustion on the single node** during rollouts (two
   generations of a pod briefly coexist): pods `Pending` with scheduling
   events. See [node and OKD troubleshooting](../troubleshooting/node-and-okd.md).
5. **Data plane task failure**: package repository unreachable, DNS, SSH,
   or a node that was changed by hand.

## 5. Resolution

Fix the cause; the reconciliation then resumes by itself. There is no
"retry" button for the control plane.

**[CHANGE]** Wrong image override — correct or remove it:

```bash
oc -n openstack patch openstackversion openstack --type=json \
  -p '[{"op":"remove","path":"/spec/customContainerImages/<field>"}]'
```

**[CHANGE]** Pod stuck on an old failure after the cause is fixed — delete
it; its controller recreates it (see
[restarting a service](../operations/03-restart-a-service.md) for what this
means for each workload type):

```bash
oc -n openstack delete pod <pod>
```

**[CHANGE]** Failed data plane deployment — fix the cause, then create a
*new* deployment with the same `servicesOverride` and a new name. Optionally
restrict it to the failed node with `spec.ansibleLimit`:

```bash
cat <<'YAML' | oc create -f -
apiVersion: dataplane.openstack.org/v1beta1
kind: OpenStackDataPlaneDeployment
metadata:
  name: edpm-update-services-2
  namespace: openstack
spec:
  nodeSets:
    - openstack-edpm
  servicesOverride:
    - update
  ansibleLimit: edpm-compute-0
YAML
```

**[CHANGE]** Unapproved InstallPlan — approve it
([02](02-operator-upgrade.md)).

When you cannot fix forward, collect evidence before anything else:

**[CHANGE]** (does not modify OpenStack, but creates a temporary namespace
and collection pod and writes to the local directory)

```bash
oc adm must-gather --image=quay.io/openstack-k8s-operators/openstack-must-gather --dest-dir=./must-gather
```

Run on the healthy lab: the image is pulled without credentials, the
collection takes about two minutes and writes about 60 MB (resources of
the OpenStack, operator and platform namespaces, pod logs, one directory
per control plane service). Treat the result as sensitive and remove it
when done.

Then decide with [04-rollback-limitations.md](04-rollback-limitations.md):
in the lab, the realistic fallback is restoring the volume snapshots taken
before the change.

## 6. Verification

Same as the verification of the operation that was in progress
([01](01-openstack-version-and-minor-update.md) section 6 or
[02](02-operator-upgrade.md) section 6), plus:

**[READ-ONLY]**

```bash
oc -n openstack get openstackversion openstack -o json \
  | jq -r '.status.conditions[] | select(.status != "True") | .type'
oc -n openstack get jobs -o json | jq -r '.items[] | select(.status.failed != null) | .metadata.name'
```

Both should print nothing.

## 7. Risks and precautions

- **Do not set `targetVersion` back** to escape a stalled update without
  understanding the state: some services already run the new images and may
  have migrated their database schema. The webhook accepts any previously
  known version (verified on the lab, on a *finished* update between two
  image sets with identical software); the result is not a supported path.
- **Do not edit Deployments, StatefulSets or image fields of service CRs by
  hand** to "help" the update: the operators overwrite them
  (see [why manual changes are reverted](../concepts/03-operators-crds-and-reconciliation.md)).
- **Do not delete PVCs or the Galera/RabbitMQ custom resources** to unblock
  a stage. That turns a stalled update into data loss.
- Deleting a failed Job is safe only for Jobs the operator recreates
  (db-sync, bootstrap); check that it reappears.
- Scaling an operator to zero stops reconciliation of that service only; the
  openstack-operator may scale it back. It is a diagnostic aid, not a pause
  button.

### Not tested, and limits of this validation

- No failure was provoked: image pull errors, failed db-sync Jobs, a failed
  Ansible task and a CSV stuck in `Pending` are described from the operator
  source, with reason and message strings that were not observed.
- The resolutions of section 5 were not executed, except the removal of an
  image override (done on a healthy platform in
  [01](01-openstack-version-and-minor-update.md)).
- Confirmed on the lab: the Ansible pod label `app=openstackansibleee`, the
  condition names, reasons and messages of a healthy update, the webhook
  message, and the must-gather image on OKD.

---

**Previous:** [Upgrading the OpenStack operators](02-operator-upgrade.md) · **Up:** [Lifecycle management](index.md) · **Next:** [Rollback: what can and cannot be undone](04-rollback-limitations.md)
