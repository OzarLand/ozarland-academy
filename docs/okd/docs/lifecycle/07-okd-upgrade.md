---
title: "Upgrading OKD"
description: "This is Phase 4 material: it concerns the platform under OpenStack."
---

# Upgrading OKD

> Status: partially validated on the lab — only the read-only parts were run on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable): current state, channel, offered updates, health gates and API deprecation queries. The upgrade itself was deliberately not executed and remains an exercise; no upgrade edge was offered to the lab at that date

## In short

- An OKD release is one payload: Kubernetes, the cluster operators and the
  node OS. Upgrading it restarts OpenStack but does not upgrade it.
- On the single-node lab an OKD upgrade includes at least one full control
  plane outage, and there is no downgrade: take volume snapshots first.
- Observed on the lab: with the settings left by the 4.22 installer,
  `oc adm upgrade` answers "No updates available".
- Read upstream, **not tested on the lab**: a newer OKD update service may
  offer updates from this version (note in section 3).
- The upgrade itself was not executed. The OpenStack operators are not
  validated on the next Kubernetes version.

This is Phase 4 material: it concerns the platform under OpenStack. Read
[06-okd-maintenance-impact.md](06-okd-maintenance-impact.md) first — on the
single-node lab an OKD upgrade includes at least one full control plane
outage.

## 1. Context

An OKD release is one versioned payload: Kubernetes, every cluster operator
(networking, ingress, DNS, OLM, ...) and the node operating system. You do
not upgrade these pieces separately and you do not use a package manager on
the node. The **Cluster Version Operator** (CVO) reads the desired release
from the `ClusterVersion` resource and upgrades the cluster operators in a
fixed order; the **Machine Config Operator** then moves the node to the new
OS image and reboots it.

Only specific version-to-version paths ("upgrade edges") are allowed. They
come from an update graph, filtered by the **channel** set on the cluster.
The lab starts on OKD 4.22, the last 4.x stream, which makes "4.22 to 5.0"
the natural exercise — once the update service offers that edge to the
installed release, which was not the case when this page was validated
(section 3).

What the OKD upgrade does **not** touch: the OpenStack operators and the
OpenStack service images ([README](index.md)). They are restarted, not
upgraded.

## 2. Read-only investigation

All **[READ-ONLY]**.

Current state and what is offered:

```bash
oc get clusterversion
oc get clusterversion version -o jsonpath='{.spec.channel}{"\n"}'
oc adm upgrade
oc get clusterversion version -o json | jq -r '.status.history[] | "\(.version)\t\(.state)\t\(.completionTime)"'
```

Cluster health gates:

**[READ-ONLY]**

```bash
oc get clusteroperators
oc get clusterversion version -o json \
  | jq -r '.status.conditions[] | "\(.type)\t\(.status)\t\(.message)"'
oc get machineconfigpool
oc get nodes
```

Will the OpenStack operators run on the target Kubernetes version?

**[READ-ONLY]**

```bash
oc -n openstack-operators get csv \
  -o custom-columns=NAME:.metadata.name,MIN_KUBE:.spec.minKubeVersion,PHASE:.status.phase
oc version
```

APIs in use that the next Kubernetes version removes (the API server counts
requests per API version):

**[READ-ONLY]**

```bash
oc get apirequestcounts -o json \
  | jq -r '.items[] | select(.status.removedInRelease != null) | "\(.metadata.name)\tremoved in \(.status.removedInRelease)"'
```

OpenStack health (an upgrade restarts everything):

**[READ-ONLY]**

```bash
oc -n openstack get openstackcontrolplane openstack
oc -n openstack get openstackversion openstack \
  -o custom-columns=TARGET:.spec.targetVersion,DEPLOYED:.status.deployedVersion
```

## 3. Expected observations

- `oc adm upgrade` prints the current version, the channel, and either a
  list of available updates or a reason why none is recommended. On the
  lab:

  ```text
  Cluster version is 4.22.0-okd-scos.10

  Upstream: https://amd64.origin.releases.ci.openshift.org/graph
  Channel: stable-scos-4
  No updates available. You may still upgrade to a specific release image with --to-image or wait for new updates to be available.
  ```

  The channel set by the installer is `stable-scos-4`. The update graph
  served for it does contain 5.0 pre-release (`5.0.0-okd-scos.ec.*`) and
  later development builds, but **no edge starting from
  `4.22.0-okd-scos.10`**: `status.availableUpdates` is `null` and there is
  no conditional update either. Whether a `stable-scos-5` channel exists was
  not tested (it would be a change).

  > **Note of 2026-11-13: upstream reading, not tested on the lab.**
  >
  > - *Observed on the lab, unchanged:* with the update source and the
  >   channel shown above, the cluster is offered no update.
  > - *Read upstream, not on the cluster:*
  >   [contribution topic 11](../../contributions/topics/11-okd-update-service-docs.md)
  >   records that OKD has had its own update service since September 2026
  >   (`updates.okd.io`, channels `stable-5.0` and `candidate-5.0`), and
  >   that a cluster installed with 4.22 keeps the previous settings: the
  >   release controller as update source and the channel `stable-scos-4`.
  >   The update graphs, read directly on 2026-11-13 from a workstation,
  >   offered updates from `4.22.0-okd-scos.10` on two of them:
  >   `5.0.0-okd-scos.2` to `.6` plus one conditional update on
  >   `updates.okd.io` with `stable-5.0`, and `5.0.0-okd-scos.0` to `.6` on
  >   the release controller with `stable-scos-5`.
  > - *Not tested:* the lab cluster was not pointed at the new service and
  >   its channel was not changed. What `oc adm upgrade` would show
  >   afterwards is deduced from the graphs, not observed, and no update to
  >   5.0 was run.
  >
  > The statements of this page about "no edge" therefore describe what the
  > lab was offered with its default settings. They do not establish that
  > no upgrade path exists.
- History: a single entry, `4.22.0-okd-scos.10  Completed`.
- `ClusterVersion` conditions on the lab: `RetrievedUpdates=True`,
  `ReleaseAccepted=True`, `Available=True`, `Failing=False`,
  `Progressing=False`, `ImplicitlyEnabledCapabilities=False`. There is no
  `Upgradeable` condition at all when nothing objects; `Upgradeable=False`
  blocks minor upgrades and its message names the operator that objects.
- All cluster operators available, machine config pool `master` updated,
  node on CentOS Stream CoreOS 10 with Kubernetes v1.35.
- `oc get apirequestcounts` answers "No resources found" on this release:
  the query for removed APIs prints nothing, **because there is no data,
  not because nothing is deprecated**. API removals must be checked from
  the Kubernetes release notes of the target version.
- The openstack-operator bundle on 18-stable declares no useful Kubernetes
  bound (`minKubeVersion: 0.0.1` in `openstack-operator.v0.8.0`). **Nothing
  in the bundle states an upper bound**, and upstream does not test on OKD: a
  target Kubernetes version newer than what the operators were built against
  (Kubernetes 1.33 client libraries on 18-stable) must be treated as
  unverified until you have tried it.

## 4. Explanation

Order of an upgrade and what you see:

1. CVO downloads and verifies the release payload.
2. Cluster operators upgrade one after another, control plane first (etcd,
   API server, controllers, scheduler), then the rest. On a single node the
   API disappears briefly several times as static pods restart.
3. OLM is upgraded as part of this; installed operators keep running.
4. The Machine Config Operator applies the new OS image: drain (nothing to
   drain to), **reboot**. Everything stops; see
   [06](06-okd-maintenance-impact.md).
5. After the reboot the remaining operators settle and `ClusterVersion`
   reports the new version as `Completed`.

Compatibility is your responsibility at one point: the third-party content
of the cluster. For this lab that means the OpenStack operators,
cert-manager and MetalLB (both installed from upstream manifests at pinned
versions). The CVO knows nothing about them.

## 5. Procedure

Pre-checks, in order:

1. Section 2 shows a healthy cluster and a healthy control plane.
2. No OpenStack update is in progress (target equals deployed).
3. Compatibility of the OpenStack operators, cert-manager and MetalLB with
   the target Kubernetes version has been checked (release notes, upstream
   issues) — or you accept this as an experiment.
4. Backups: etcd, exported resources, and, because there is no downgrade,
   **volume snapshots of the lab VMs**
   ([05](05-backup-and-restore.md), [04](04-rollback-limitations.md)).
5. Read the known issues of the target release (the OKD project tracks them
   in its issue tracker); several affect single-node clusters.

**None of the [CHANGE] commands below was executed on the lab.**

**[CHANGE]** If no update is offered, check the channel. OKD on CentOS
Stream CoreOS uses channels named `stable-scos-<major>` (`stable-scos-4` is
confirmed on the lab; the name for the 5.x stream is not):

```bash
oc adm upgrade channel stable-scos-4
oc adm upgrade
```

**[CHANGE]** Start the upgrade to a version listed by `oc adm upgrade`:

```bash
oc adm upgrade --to=<version>
```

`--to-latest` picks the newest offered version. Avoid `--to-image` with
`--allow-explicit-upgrade` and `--force` unless you are deliberately leaving
the supported graph: they bypass the edge and signature checks. With no
edge offered, as on the lab at validation time, `--to-image` is the only
way to start the exercise: that is precisely the unsupported case, to be
attempted only with volume snapshots at hand. A change of update source and
channel may offer an edge instead; it was read upstream and not tested (see
the note in section 3).

**[READ-ONLY]** Follow (the API will be unreachable at times; just retry):

```bash
watch -n 30 'oc get clusterversion; oc get clusteroperators | awk "NR==1 || \$3!=\"True\" || \$4!=\"False\" || \$5!=\"False\""'
oc get machineconfigpool
oc get nodes
```

If it stalls, all **[READ-ONLY]**:

```bash
oc get clusterversion version -o json | jq -r '.status.conditions[] | "\(.type)\t\(.status)\t\(.message)"'
oc get clusteroperator <name> -o json | jq -r '.status.conditions[] | "\(.type)\t\(.status)\t\(.message)"'
oc -n openshift-cluster-version logs deployment/cluster-version-operator --tail=50
oc get machineconfigpool master -o json | jq -r '.status.conditions[] | "\(.type)\t\(.status)\t\(.message)"'
```

The `ClusterVersion` message names the operator it is waiting for; that
operator's conditions name the reason. See also
[node and OKD troubleshooting](../troubleshooting/node-and-okd.md).

## 6. Verification

**[READ-ONLY]**

```bash
oc get clusterversion
oc get clusterversion version -o json | jq -r '.status.history[0] | "\(.version)\t\(.state)"'
oc get nodes -o wide
oc get clusteroperators | awk 'NR == 1 || $3 != "True" || $5 != "False"'
oc get machineconfigpool
oc -n openstack-operators get csv
oc -n openstack-operators get pods --field-selector=status.phase!=Running
oc -n openstack get openstackcontrolplane openstack
```

Expected: history shows the new version `Completed`; the node reports the
new Kubernetes and OS versions; the CSV is still `Succeeded`; the control
plane is `Ready`. Then the checks of
[06](06-okd-maintenance-impact.md) section 6 and `tests/smoke-test.sh`.
Also confirm that MetalLB still announces its addresses and that
cert-manager is running — they are the pieces installed outside OKD.

## 7. Risks and precautions

- **No downgrade.** A started upgrade must be driven to completion or the
  cluster restored from before it.
- **Unverified combination.** OpenStack operators 18-stable on the
  Kubernetes version of the 5.0 stream is not a combination this lab has
  validated. Possible failure modes: an operator using a removed API, an
  admission webhook incompatibility, OLM behaviour changes. Have the
  snapshots.
- **Network configuration survival.** The lab patched the cluster network
  operator (`routingViaHost`, `ipForwarding`) and relies on static node
  interfaces; verify both after the upgrade
  (`oc get network.operator cluster -o jsonpath='{.spec.defaultNetwork.ovnKubernetesConfig.gatewayConfig}'`).
- **Known single-node hazards** reported upstream for recent releases:
  nodes not coming back after an unclean shutdown, and etcd defragmentation
  problems (the latter on multi-member clusters). Read the current issue
  list before starting.
- **Time.** Expect one to two hours on the lab, with the OpenStack APIs
  unavailable for a significant part of it.
- Once on a stream that still receives releases, patch (z-stream) upgrades
  follow the same procedure and are lower risk; practising those first is a
  better learning sequence than starting with a major-version edge.

The lab-specific network settings are in place before any upgrade: the
command above prints
`{"ipForwarding":"Global","ipv4":{},"ipv6":{},"routingViaHost":true}`, and
it survived a node reboot and a full restart of the lab.

### Not tested, and limits of this validation

- **The upgrade was not executed**, on purpose: the lab is the only
  validated environment and there is no way back short of volume
  snapshots. Sections 4, 5 (from the first [CHANGE]) and 6 describe what
  is expected, not what was observed.
- Not known from the lab: the channel name for the 5.x stream, when (or
  whether) an edge from `4.22.0-okd-scos.10` is published, the total
  duration, and above all the behaviour of the OpenStack operators,
  cert-manager and MetalLB on the next Kubernetes version.
- Pointing the cluster at the newer OKD update service, and what
  `oc adm upgrade` then offers, was not tested. The upstream reading is in
  [contribution topic 11](../../contributions/topics/11-okd-update-service-docs.md)
  and summarised in the note of section 3.

---

**Previous:** [Impact of OKD maintenance on OpenStack](06-okd-maintenance-impact.md) · **Up:** [Lifecycle management](index.md)
