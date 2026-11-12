# Upgrading the OpenStack operators

> Status: partially validated on the lab — read-only commands and the catalog refresh were run on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); the catalog offered no newer bundle, so no InstallPlan could be approved and the replacement of the operators by OLM (section 5, steps 2 to 4) was not executed

## 1. Context

You want newer operators: bug fixes in the controllers, new fields in the
custom resources, or a newer set of service images to become *available*.
The closest Kolla-Ansible analogy is upgrading the `kolla-ansible` package
itself — except that here the tool runs permanently in the cluster and
starts acting as soon as it is replaced.

The operators are installed and upgraded by OLM (Operator Lifecycle
Manager), a standard OKD component. Four objects in the
`openstack-operators` namespace form the chain:

| Object | Role | Lab value |
|---|---|---|
| `CatalogSource` | A container image holding a catalog of operator bundles; OLM runs it as a pod and queries it | `openstack-operator-index`, image from `OPENSTACK_OPERATOR_INDEX` |
| `Subscription` | "Keep package X from channel Y of that catalog installed" | `openstack-operator`, channel `alpha`, `installPlanApproval: Manual` |
| `InstallPlan` | A concrete, computed list of things to install for one version; waits for approval in manual mode | generated names `install-xxxxx` |
| `ClusterServiceVersion` (CSV) | One installed version of the operator: its Deployments, permissions, CRDs it owns | `openstack-operator.v<version>` |

The CSV itself installs a single Deployment,
`openstack-operator-controller-init`. That controller reconciles the
`OpenStack` initialization resource (`openstack` in `openstack-operators`)
and creates `openstack-operator-controller-manager` and the twenty service
operator Deployments (keystone-operator, nova-operator, ...) at the version
it embeds. There is a single bundle: service operators are not upgraded
individually.

## 2. Read-only investigation

**[READ-ONLY]** What is installed and what the subscription sees:

```bash
oc -n openstack-operators get csv
oc -n openstack-operators get subscription openstack-operator \
  -o custom-columns=CHANNEL:.spec.channel,APPROVAL:.spec.installPlanApproval,INSTALLED:.status.installedCSV,CURRENT:.status.currentCSV,STATE:.status.state
oc -n openstack-operators get installplan
```

**[READ-ONLY]** Which catalog image is in use, and whether its pod is
healthy:

```bash
oc -n openstack-operators get catalogsource openstack-operator-index \
  -o custom-columns=IMAGE:.spec.image,STATE:.status.connectionState.lastObservedState
oc -n openstack-operators get pods -l olm.catalogSource=openstack-operator-index \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

**[READ-ONLY]** Health before touching anything:

```bash
oc -n openstack-operators get openstack openstack
oc -n openstack-operators get pods
oc -n openstack get openstackcontrolplane openstack
oc -n openstack get openstackversion openstack \
  -o custom-columns=TARGET:.spec.targetVersion,AVAILABLE:.status.availableVersion,DEPLOYED:.status.deployedVersion
```

**[READ-ONLY]** Minimum Kubernetes version required by the installed
operator, and the cluster version:

```bash
oc -n openstack-operators get csv -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.minKubeVersion}{"\n"}{end}'
oc version
```

## 3. Expected observations

Observed on the lab at rest:

```text
NAME                        DISPLAY     VERSION   REPLACES   PHASE
openstack-operator.v0.8.0   OpenStack   0.8.0                Succeeded

CHANNEL   APPROVAL   INSTALLED                   CURRENT                     STATE
alpha     Manual     openstack-operator.v0.8.0   openstack-operator.v0.8.0   AtLatestKnown
```

- Idle state: `INSTALLED` equals `CURRENT`, `STATE` is `AtLatestKnown`, all
  InstallPlans have `APPROVED true` (one plan, the installation).
- The catalog pod `imageID` is the digest really installed
  (`...openstack-operator-index@sha256:27748cea...` at validation time,
  recorded in full in [versions](../versions.md)).
- The CSV declares `minKubeVersion: 0.0.1`; `oc version` reports the
  Kubernetes version of the cluster (v1.35).
- Upgrade available: `CURRENT` names a newer CSV than `INSTALLED`, `STATE` is
  `UpgradePending`, and one InstallPlan shows `APPROVED false`.
- If the catalog is referenced by a moving tag (`18-stable-latest`), nothing
  happens until the catalog pod is restarted with a newer image: a running
  pod never re-pulls its tag by itself (unless the CatalogSource defines
  `spec.updateStrategy.registryPoll`, which the lab does not).
- If the catalog is pinned by digest, nothing ever changes until you edit
  the digest.

**A newer catalog image is not necessarily an OLM upgrade on 18-stable.**
The catalog of the lab contains one channel (`alpha`) with a single entry,
`openstack-operator.v0.8.0`, and that CSV has no `replaces`, `skips` or
`olm.skipRange`:

**[READ-ONLY]**

```bash
oc -n openstack-operators get packagemanifest openstack-operator -o json \
  | jq -r '.status.channels[] | "\(.name)\t\(.currentCSV)\t\([.entries[].name] | join(","))"'
```

The upstream build keeps the bundle version fixed at `0.8.0` on this branch
and only changes the release suffix (`0.8.0-<timestamp>`) and the image
digests inside it. A rebuilt catalog therefore still offers a CSV named
`openstack-operator.v0.8.0`, which OLM considers already installed: the
Subscription is expected to stay `AtLatestKnown`. (Derived from the upstream
build files and from the catalog content; during the validation the tag
still pointed to the installed digest, so this case could not be observed.)
In that situation the only ways to get the newer operators are to remove
and reinstall the Subscription and CSV — the CRDs and your resources stay —
or to rebuild the lab with the new digest. Neither was exercised.

## 4. Explanation

Manual approval turns "a newer bundle exists in the catalog" and "the
operators are replaced" into two separate events. The InstallPlan is the
checkpoint between them. With `Automatic` approval (the upstream development
default) the operators would be replaced as soon as the catalog content
changes.

What an operator upgrade changes:

- The operator Deployments in `openstack-operators` and their images.
- CRD definitions (new fields, new defaults) and admission webhooks.
- `status.availableVersion` of `OpenStackVersion`, when the bundle embeds new
  service images.

What it does not change:

- `spec.targetVersion`, therefore the service images
  ([01](01-openstack-version-and-minor-update.md)).
- Your custom resources. But new controllers reconcile existing resources
  with new code: a changed default or template can still cause a rollout of
  a service with the *same* image. Treat an operator upgrade as a change to
  the running platform, not as a pure tooling update.

## 5. Procedure

Prerequisites: everything `Ready` (section 2); no service update in
progress (target, available and deployed versions equal); CRs and secrets
exported ([05](05-backup-and-restore.md)).

**[CHANGE]** Step 1 — make the newer catalog visible. Pinned by digest
(recommended): point the CatalogSource to the new digest.

```bash
oc -n openstack-operators patch catalogsource openstack-operator-index --type=merge \
  -p '{"spec":{"image":"quay.io/openstack-k8s-operators/openstack-operator-index@sha256:<new-digest>"}}'
```

Moving tag: restart the catalog pod so that it pulls the tag again.

**[CHANGE]**

```bash
oc -n openstack-operators delete pod -l olm.catalogSource=openstack-operator-index
```

Observed on the lab with the moving tag: the new pod pulls the image again
(`imagePullPolicy: Always`, event "Pulling image ...:18-stable-latest"),
the CatalogSource reports `TRANSIENT_FAILURE` for about 20 seconds, then
`READY`. The installed operators are not affected by a catalog restart. The
tag still resolved to the same digest, so nothing else happened: the
Subscription stayed `AtLatestKnown` and no InstallPlan was created.

Record the new value in `lab.env` (`OPENSTACK_OPERATOR_INDEX`) so that a
rebuild of the lab installs the same operators.

**[READ-ONLY]** Step 2 — wait for OLM to compute the upgrade and read what
it proposes:

```bash
oc -n openstack-operators get subscription openstack-operator -o jsonpath='{.status.state}{"\t"}{.status.currentCSV}{"\n"}'
oc -n openstack-operators get installplan
plan="$(oc -n openstack-operators get installplan -o json | jq -r '.items[] | select(.spec.approved == false) | .metadata.name')"
oc -n openstack-operators get installplan "${plan}" -o jsonpath='{.spec.clusterServiceVersionNames}{"\n"}'
```

**[CHANGE]** Step 3 — approve:

```bash
oc -n openstack-operators patch installplan "${plan}" --type=merge -p '{"spec":{"approved":true}}'
```

**[READ-ONLY]** Step 4 — follow:

```bash
oc -n openstack-operators get csv -w
oc -n openstack-operators get pods -w
oc -n openstack-operators get openstack openstack -o json \
  | jq -r '.status.conditions[] | "\(.type)\t\(.status)\t\(.message)"'
```

The old CSV goes to `Replacing` then disappears; the new one goes through
`Pending`, `Installing`, `Succeeded` (not observed on the lab, see the
status line).

What was observed is the second half, when the content of the installed
CSV changes (done by hand for the exercise of
[01](01-openstack-version-and-minor-update.md), section 5.2): the CSV went
`Installing` then `Succeeded` in about 20 seconds,
`openstack-operator-controller-init` was replaced, then
`openstack-operator-controller-manager` and **all** service operator
Deployments were deleted and recreated — the controller manager is briefly
`NotFound`. About 95 seconds after the change every operator pod was
running again and `availableVersion` showed the new value. The `OpenStack`
resource has three conditions to follow: `Ready`,
`OpenStackOperatorDeploymentsReadyCondition` and
`OpenStackOperatorReadyCondition`. No OpenStack service pod was restarted
and the control plane stayed `Ready`.

## 6. Verification

**[READ-ONLY]**

```bash
oc -n openstack-operators get csv
oc -n openstack-operators get openstack openstack
oc -n openstack-operators get pods --field-selector=status.phase!=Running
oc -n openstack get openstackcontrolplane openstack
oc -n openstack get openstackdataplanenodeset
oc -n openstack get openstackversion openstack \
  -o custom-columns=TARGET:.spec.targetVersion,AVAILABLE:.status.availableVersion,DEPLOYED:.status.deployedVersion
oc -n openstack get pods --sort-by=.status.startTime | tail -15
```

Expected: one CSV, `Succeeded`; `OpenStack` resource `Ready`; control plane
back to `Ready` (it may go through a not-ready period while services are
re-reconciled); `AVAILABLE` possibly newer than `DEPLOYED`. The last command
shows which service pods were restarted by the new controllers. Then run
`tests/smoke-test.sh`.

## 7. Risks and precautions

- **No downgrade.** OLM does not install an older CSV over a newer one, and
  CRD changes are not reverted ([04](04-rollback-limitations.md)).
- The catalog only offers the head of its channel. You cannot pick an
  intermediate version from a given catalog image; choosing the catalog
  image (digest) *is* choosing the version.
- During the replacement there is a window without controllers or webhooks:
  running services are unaffected, but `oc apply` on OpenStack resources may
  be rejected, and nothing is reconciled. Do not make changes during it.
- A new controller may restart services (see section 4). Plan the same
  outage window as for a configuration change.
- A moving catalog tag makes the lab non-reproducible: record the digest.
- If the new operator requires a newer Kubernetes than the cluster runs, the
  CSV stays in `Pending` with a requirement message; upgrade OKD first
  ([07](07-okd-upgrade.md)).

### Not tested, and limits of this validation

- No newer bundle was offered during the validation: the approval of an
  InstallPlan and the `Replacing` sequence remain to be exercised, as does
  the reinstall path described in section 3.
- The catalog pod label (`olm.catalogSource=openstack-operator-index`) and
  the state string `AtLatestKnown` are confirmed; `UpgradePending` was not
  seen.
