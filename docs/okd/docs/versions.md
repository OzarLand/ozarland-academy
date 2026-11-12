# Versions and validation status

This page is the single place that states which versions the lab uses, why
they were selected, and what has actually been tested. Update it whenever a
version in `config/lab.env.example` changes.

## Selected versions

| Component | Version | Kubernetes | Source of the choice |
|---|---|---|---|
| OKD | `4.22.0-okd-scos.10` | 1.35 | Last release of the 4.22 stream; node OS CentOS Stream CoreOS 10 |
| OpenStack operators | branch `18-stable` (catalog image tag `18-stable-latest`; digest validated: see below) | no usable lower bound declared | Stable branch; the installed ClusterServiceVersion (`openstack-operator.v0.8.0`) declares `minKubeVersion: 0.0.1`. Installed and run on Kubernetes 1.35 in the lab |
| OpenStack services | 2023.1 "Antelope" container images (`quay.io/podified-antelope-centos9`, tag `current-podified`) | – | Default images of the `18-stable` operators |
| Data plane node OS | CentOS Stream 9 | – | Matches the Antelope data plane images and packages |
| cert-manager | `v1.21.3` | – | Latest upstream release at the time of writing |
| MetalLB | `v0.16.2` | – | Latest upstream release at the time of writing |
| frr-k8s (FRRConfiguration CRD only) | `v0.0.27` | – | Version paired with the MetalLB release; the OpenStack infra-operator watches this kind and does not start without it |

### Operator catalog actually validated

The tag `18-stable-latest` moves. Everything marked as tested on this page
was run with the catalog image it pointed to on 2026-11-11:

```text
quay.io/openstack-k8s-operators/openstack-operator-index@sha256:27748ceae9dbc7368a44a6d1c531c48cdbd9d102bc594b15b0644bf32f6ef5ae
```

It installs `openstack-operator.v0.8.0`, release `0.8.0-1794211973` (the
value shown as `availableVersion` by `OpenStackVersion`). **To reproduce
the validated lab, set `OPENSTACK_OPERATOR_INDEX` in `lab.env` to this
digest reference instead of the tag.** With the tag, an installation made
later gets whatever upstream has merged since, which this page says
nothing about. Read the digest of a running lab with:

```bash
oc -n openstack-operators get pods -l olm.catalogSource=openstack-operator-index \
  -o jsonpath='{.items[0].status.containerStatuses[0].imageID}{"\n"}'
```

### Why these and not others

- **OpenStack operators: `18-stable`, not `main`.** The `main` branch (and
  `19.0-beta`) deploys images built from OpenStack master on CentOS
  Stream 10 and changes daily. `18-stable` is the branch with the longest
  history and it corresponds to the documentation of the downstream product
  built from the same code, which is the most complete operational
  documentation available for these operators.
- **OKD 4.22, not 5.0.** OKD 5.0 (Kubernetes 1.36) is the stream currently
  receiving updates. The operators only declare a *minimum* Kubernetes
  version and upstream does not test them on OKD at all, so compatibility
  with any OKD release has to be established by testing. 4.22 was chosen as
  the more conservative starting point, with the OKD upgrade to 5.0 as a
  later exercise. On 2026-11-12 the update service offered no upgrade edge
  to the installed release on its default channel (`stable-scos-4`):
  see [the OKD upgrade page](lifecycle/07-okd-upgrade.md). The 4.22 stream
  no longer receives new builds.
- **Not every combination works.** Do not assume a newer OKD, a newer
  operator branch or a different node OS can be swapped in. In particular
  the data plane node OS must match the container images (CentOS Stream 9
  for `18-stable`, CentOS Stream 10 for `main`).

### Known upstream particularities on OKD

| Topic | Detail | Lab handling |
|---|---|---|
| Vendor operator catalog absent | cert-manager, MetalLB, NMState and LVM Storage operators are not installable from OKD's default catalogs | Upstream release manifests for cert-manager and MetalLB; static network configuration at install time; local volumes |
| Telemetry image | The default Apache image used by Ceilometer comes from a registry requiring a vendor account | Telemetry disabled |
| Bare-metal operator | Fails to start without the Metal3 `BareMetalHost` CRD | The CRD was already present on the validated OKD 4.22 cluster; the operator step installs it only when it is missing |
| Upstream OKD mode of `install_yamls` | Unmaintained; its MetalLB installation path is reported broken | Not used |

## Validation status

Legend:

- **Tested** — executed successfully on the lab infrastructure.
- **Partially tested** — executed with deviations or with open issues, described in the notes.
- **Static checks only** — linted and rendered offline; never executed.
- **Documented only** — written from upstream source and documentation; never executed.

| Item | Status | Notes |
|---|---|---|
| Shell scripts (ShellCheck), Python helper (ruff), YAML (yamllint) | Tested | `make lint` |
| Manifest templates render to valid YAML | Tested | `tests/render-templates.sh` |
| Terraform module | Tested | `apply` on one tenant OpenStack cloud, with floating IPs; the path without floating IPs and the bastion access network were not deployed |
| Host cloud prerequisites checks | Partially tested | Checked while preparing one deployment, not as a separate pass over every command |
| Bastion setup and DNS | Tested | Including a bastion reboot |
| OKD agent-based installation (ISO boot from volume) | Tested | Behind an HTTPS proxy, with `ISO_BLANK_SYSTEM_AREA=true` and the bastion as time source; about 46 minutes |
| Platform services (storage, cert-manager, MetalLB) on OKD | Tested | The SCC grants for MetalLB are sufficient |
| OpenStack operators installation through OLM on OKD 4.22 | Tested | `openstack-operator.v0.8.0` installs and all service operators run on Kubernetes 1.35 |
| OpenStack control plane | Tested | About 10 minutes until all pods run; node memory about 60 % of 32 GiB |
| OpenStack data plane on a pre-provisioned VM of a tenant cloud | Tested | One compute node with KVM, behind an HTTPS proxy; about 21 minutes. QEMU emulation path not executed |
| Smoke and functional tests | Tested | `tests/smoke-test.sh --functional` boots an instance |
| Operations guide scenarios | Partially tested | Every page was run against the lab on 2026-11-11; each page carries its own status line. Not executed: rotation of the database passwords |
| Troubleshooting runbooks | Partially tested | Read-only commands and the safe reproductions were run on 2026-11-11; each page states in its status line what was not provoked (faults that would risk an unrecoverable lab, host cloud faults, QEMU emulation) |
| Lifecycle: `OpenStackVersion`, single-image override, staged minor update of both planes | Tested | 2026-11-12. The newer version was simulated with the upstream helper (`0.8.0-1794211973` to `0.8.1-1794211973` and back): real replacement of every image and a package update of the compute node, but the same OpenStack package versions on both sides |
| Lifecycle: operator upgrade through OLM | Partially tested | Inspection and catalog refresh run; the catalog offered no newer bundle, so no InstallPlan was approved. On `18-stable` the bundle name does not change between builds, see the page |
| Lifecycle: failed upgrade, rollback limits | Partially tested | Read-only commands, webhook refusals, healthy-update signatures. No failure provoked, no downgrade |
| Lifecycle: backups | Tested | Export of resources and Secrets, `GaleraBackup` for both database instances, etcd backup, volume snapshots of the stopped VMs |
| Lifecycle: restores | Documented only | `GaleraRestore` accepted by a server-side dry run only; etcd restore and snapshot rollback never executed |
| Lifecycle: OKD node reboot, graceful shutdown and restart of the lab, compute node reboot | Tested | Recovery without intervention in 3 to 6 minutes, except the metadata agent limitation below. MachineConfig change and unclean stop not executed |
| Lifecycle: OKD upgrade | Documented only | Read-only pre-checks run; the upgrade was deliberately not executed |

## Known limitations

- **Single node, no high availability.** Any restart of the OKD node is an
  outage of the OpenStack control plane.
- **No persistent block or object storage service.** Cinder and Swift are
  disabled; instances use ephemeral disks on the compute node.
- **No public connectivity for instances.** Floating IPs of the lab cloud
  are only reachable inside the lab.
- **Local storage.** Control plane data lives on the OKD node root volume;
  losing that volume loses the cloud.
- **Moving catalog tag.** Until `OPENSTACK_OPERATOR_INDEX` is pinned to a
  digest, two installations on different days may install different
  operator builds. The validated digest is given above.
- **EOL platform stream.** OKD 4.22 receives no further builds, and no
  upgrade edge to 5.0 was offered to the installed release at validation
  time.
- **One environment.** Everything was validated on a single deployment, on
  one host cloud, with KVM on the compute node and behind an HTTPS proxy.
- **OVN metadata agent after an OKD node reboot.** After a reboot of the
  OKD node alone, the metadata agent of the compute node was once left
  disconnected from the OVN southbound database while still reported
  alive; new instances then get no metadata. It did not happen after a
  restart of the whole lab or a compute reboot. Check the agents after any
  control plane outage; the remedy is a restart of
  `edpm_ovn_metadata_agent`
  ([runbook](troubleshooting/node-and-okd.md)).
- **Password rotation is a two-step change.** Changing a service password
  in `osp-secret` rolls the service with the new value, but the operator
  does not change the password of the Keystone user: the service fails
  (HTTP 503) with every condition `True` until the Keystone user is set to
  the same value
  ([passwords and secrets](operations/07-passwords-and-secrets.md)).
  Rotation of the database passwords was not executed.
- **The data plane update also updates the host.** The `update` service
  runs a full package update of the compute node, kernel included, and
  does not reboot it.
- **Database backups are not pruned.** With the operators validated here,
  the `retention` of `GaleraBackup` deletes nothing; each backup also
  keeps a full copy of the database on its volume.
- **Short-lived certificates during the first day.** A cluster stopped, or
  a volume snapshot taken, during the first 24 hours and started after
  that delay comes back with expired node certificates
  ([maintenance impact](lifecycle/06-okd-maintenance-impact.md)).
- **No restore has ever been executed**, and the OKD upgrade has not been
  attempted.
