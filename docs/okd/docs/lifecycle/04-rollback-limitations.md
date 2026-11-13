# Rollback: what can and cannot be undone

> Status: partially validated on the lab — read-only commands, the reversal of an image override and a return to a previous `targetVersion` between two image sets with identical software were run on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); no snapshot restore, rebuild or real downgrade was executed, and the other rows of section 4 are not exercised

## In short

- Declarative configuration is reversible: apply the previous content of
  the resource. State and versions are not.
- No downgrade is supported for the OpenStack services, the operators or
  OKD.
- Recovery is prepared **before** the change: keep the previous resource,
  take the backups of [05](05-backup-and-restore.md).
- On the lab, the only real "undo" of a version change is a set of volume
  snapshots of the VMs taken while the cluster is shut down. Taking them
  was validated; restoring them was not.
- Rebuilding at pinned versions is a legitimate rollback for a lab.

## 1. Context

With Kolla-Ansible a common reflex after a bad upgrade is "redeploy the
previous tag". It works more often than it should, because the deployment
tool is stateless and containers are replaced wholesale. In an
operator-managed platform, three of the four version axes
([README](README.md)) have **no downgrade path**. Knowing this before a
change is what makes the change safe.

## 2. Read-only investigation

Before any change, record the state you might want to return to. All
**[READ-ONLY]**.

```bash
oc get clusterversion version -o jsonpath='{.status.desired.version}{"\n"}'
oc -n openstack-operators get csv -o custom-columns=NAME:.metadata.name,PHASE:.status.phase
oc -n openstack-operators get catalogsource openstack-operator-index -o jsonpath='{.spec.image}{"\n"}'
oc -n openstack get openstackversion openstack \
  -o custom-columns=TARGET:.spec.targetVersion,AVAILABLE:.status.availableVersion,DEPLOYED:.status.deployedVersion
oc -n openstack get openstackversion openstack -o json | jq -r '.status.containerImageVersionDefaults | keys[]'
oc -n openstack get openstackcontrolplane openstack -o jsonpath='{.metadata.generation}{"\n"}'
```

## 3. Expected observations

A healthy lab at rest: one CSV, the three OpenStack versions equal, and a
catalog image you can name exactly (a digest, not just a tag).

On the lab as installed, the catalog command prints a tag
(`...openstack-operator-index:18-stable-latest`), which does not identify
what is installed. The digest is on the catalog pod:

**[READ-ONLY]**

```bash
oc -n openstack-operators get pods -l olm.catalogSource=openstack-operator-index \
  -o jsonpath='{.items[0].status.containerStatuses[0].imageID}{"\n"}'
```

Since 2026-11-12 the running lab is pinned: its CatalogSource was moved
from the tag to the digest it was already running, so the catalog command
prints a digest there
([knowledge base](../knowledge-base/okd-olm-and-operators.md#is-the-catalog-pinned-to-a-digest-and-how-do-i-move-a-running-lab-from-a-tag-to-a-digest)).

`containerImageVersionDefaults` lists every version the operator
installation has known, including versions no longer deployed. The control
plane `generation` is only a counter of spec changes: record it to detect
that something changed, not to go back.

## 4. Explanation: reversibility per kind of change

| Change | Reversible? | How / why not |
|---|---|---|
| Configuration in the `OpenStackControlPlane` CR (`customServiceConfig`, replicas, enabling a service) | **Yes** | Apply the previous content of the CR; the operator rolls services back to the old configuration. Keep the previous YAML (Git, or `oc get -o yaml` before the change). |
| Disabling a service that was enabled | Partly | The pods go away; its database, Keystone entries and PVCs may remain, or be deleted, depending on the service. Not a clean "undo". |
| Data stored by services (rows, images, queues) | No, except from backup | Reconciliation restores *declared state*, never data. |
| A single image override in `customContainerImages` | **Yes**, if no schema migration ran | Remove the override; the previous image is rolled out. Done on the lab with Keystone: about one minute each way. |
| OpenStack service version (`targetVersion`) | **No supported downgrade** | No downgrade procedure exists upstream. db-sync Jobs migrate schemas forward only, and Galera, RabbitMQ and OVN database files written by a newer version are not guaranteed readable by an older one. The webhook nevertheless *accepts* a previously known version and the operator then runs the same staged sequence towards the old images. On the lab this brought the platform back cleanly, but between two image sets containing the same software versions — a change of image references, not a downgrade. |
| Operator version (CSV) | **No** | OLM only moves forward along the upgrade graph. CRDs are cluster-wide and are upgraded in place; resources may already be stored with new fields. Removing and reinstalling an older operator is a rebuild, not a rollback. |
| OKD version | **No** | Downgrading an OKD cluster is not supported; etcd and node OS move forward. The only way back is restoring the cluster from before the upgrade. |
| Data plane node packages and containers | Containers yes, packages no | A data plane deployment installs the containers of the target version, older ones included (observed). Packages updated by the `update` service (`dnf update`, kernel included) are not downgraded and host state is not handled. Rebuild the node instead (it is a pre-provisioned VM: recreate it and redeploy). |
| Deleting a PVC with `Retain` volumes (lab storage) | Data survives on disk | The PV becomes `Released` and keeps its directory; reuse is manual. See [storage troubleshooting](../troubleshooting/storage.md). |
| Deleting the `OpenStackControlPlane` CR | **No** | Everything it owns is garbage-collected. Treat as destructive. |

The asymmetry to remember: **declarative configuration is reversible, state
and versions are not.**

## 5. Procedure: making changes recoverable

Since rollback mostly does not exist, recovery has to be prepared *before*
the change.

1. **Configuration changes** — keep the previous CR. The rendered manifests
   on the bastion (`.work/rendered/`) and the templates in Git are the
   reference; export the live object when in doubt:

   **[READ-ONLY]**

   ```bash
   oc -n openstack get openstackcontrolplane openstack -o yaml > controlplane-before.yaml
   ```

2. **Version changes (any axis)** — take the backups described in
   [05-backup-and-restore.md](05-backup-and-restore.md): exported resources
   and secrets, a database backup, an etcd backup. A database restore and
   an etcd restore were executed on the lab from such backups; what each
   one brings back, and what it leaves inconsistent, is in section 5.5 of
   that page.

3. **The lab-grade rollback: volume snapshots of the lab VMs.** The lab runs
   on virtual machines whose disks are volumes of the host cloud. A
   consistent snapshot of the OKD node volume (and the compute node volume)
   taken while the cluster is cleanly shut down captures *all four axes at
   once*. Restoring those snapshots is the only real "undo" for an OKD
   upgrade, an operator upgrade or a service update. Taking them was
   validated on the lab; restoring them was not. The procedure and its
   constraints (shutdown first, certificate validity) are in
   [05](05-backup-and-restore.md) and
   [06](06-okd-maintenance-impact.md).

4. **Change one axis at a time.** After a combined change you cannot tell
   which axis broke the platform, and no partial rollback exists.

5. **Rebuild as a strategy.** The lab is reproducible from this repository.
   For a lab, "destroy and redeploy at the previous pinned versions" is a
   legitimate rollback, provided the pinned versions (OKD release, catalog
   digest) were recorded. This is why `lab.env` should pin the catalog by
   digest.

## 6. Verification

After restoring snapshots or rebuilding: run `tests/smoke-test.sh`, then
compare the version commands of section 2 with the values recorded before
the change.

After reverting a configuration change:

**[READ-ONLY]**

```bash
oc -n openstack get openstackcontrolplane openstack
oc -n openstack get pods --sort-by=.status.startTime | tail
```

The control plane returns to `Ready` and the affected pods have been
recreated.

## 7. Risks and precautions

- A snapshot taken while the cluster is running is crash-consistent at best:
  etcd and Galera may need recovery after restore. Shut down cleanly first.
- A snapshot older than the cluster certificate validity cannot simply be
  booted and used; see the certificate notes in
  [06](06-okd-maintenance-impact.md). This matters most for a snapshot
  taken during the first day of the cluster, when the certificates on disk
  are the initial ones valid for 24 hours.
- Restoring only the OKD node while the compute node keeps newer state (or
  the opposite) creates a control plane / data plane mismatch: snapshot and
  restore them together.
- In production none of the lab shortcuts apply: there, the answer to "no
  rollback" is staged rollouts, tested backups and a pre-production
  environment. The lab is where you learn why.

### Not tested, and limits of this validation

- Restoring volume snapshots and rebuilding at pinned versions were not
  executed.
- The rows on the operator version, the OKD version, the deletion of the
  control plane resource and a real service downgrade are derived from
  upstream source and documentation, not exercised.
- Configuration reversal and the effect of disabling a service are covered
  by the [operations](../operations/README.md) pages, with their own status
  lines.

---

**Previous:** [Investigating a failed or stalled upgrade](03-failed-upgrade.md) · **Up:** [Lifecycle management](README.md) · **Next:** [Backup and restore](05-backup-and-restore.md)
