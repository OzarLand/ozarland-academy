# Lifecycle management

> Status: partially validated on the lab — the pages of this directory were run against the lab on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); each page states in its status line what was not executed (an operator upgrade through OLM, restores, provoked failures, the OKD upgrade)

With Kolla-Ansible, "the version of the platform" is essentially one thing:
the `openstack_release` and image tags in `globals.yml`, applied by one
command. In an operator-managed deployment there are **four independent
version axes**, each with its own mechanism, its own pace and its own failure
modes. Most lifecycle mistakes come from confusing them.

## The four axes

| Axis | What it versions | Who changes it | How you trigger it | Where you read it |
|---|---|---|---|---|
| 1. OKD | Kubernetes, the node OS (CentOS Stream CoreOS), cluster operators | Cluster Version Operator | `oc adm upgrade` | `oc get clusterversion` |
| 2. OpenStack operators | The controllers (openstack-operator and the service operators), their CRDs and webhooks | OLM (Operator Lifecycle Manager) | New catalog content, then approving an InstallPlan | `oc -n openstack-operators get csv` |
| 3. OpenStack services | The service container images (Keystone, Nova, Galera, OVN, ...) on the control plane and on compute nodes | openstack-operator, through the `OpenStackVersion` resource | Setting `spec.targetVersion` | `oc -n openstack get openstackversion` |
| 4. Data plane host | Packages and OS of the compute nodes (CentOS Stream) | Ansible jobs started by a data plane deployment | An `OpenStackDataPlaneDeployment` with the update services | The node itself (`rpm`, `podman ps`) |

Key consequences:

- **Upgrading the operators does not upgrade OpenStack.** A new operator
  bundle only *publishes* a newer set of service images as
  `status.availableVersion`. Service containers keep running the old images
  until you set `spec.targetVersion`
  ([01](01-openstack-version-and-minor-update.md),
  [02](02-operator-upgrade.md)).
- **Upgrading OKD does not upgrade the operators or OpenStack**, but it
  restarts everything, because the single node reboots
  ([06](06-okd-maintenance-impact.md)).
- **The control plane does not update compute nodes by itself.** The data
  plane only changes when you create a deployment
  ([01](01-openstack-version-and-minor-update.md)).

## How the axes depend on each other

```text
OKD / Kubernetes version
   └── must be supported by ──> operator bundle (CSV minKubeVersion, API usage)
          └── publishes ──> availableVersion (a set of service image references)
                 └── targetVersion applies it to ──> control plane pods
                        └── then, by explicit deployments ──> data plane containers and packages
```

Ordering rules that follow from this:

1. Before an OKD upgrade, check that the installed operator bundle supports
   the target Kubernetes version ([07](07-okd-upgrade.md)).
2. Upgrade operators before services: a service update is only possible to a
   version the running operator knows about.
3. Within a service update, OVN on the control plane goes first, then OVN on
   the data plane, then the rest of the control plane, then the rest of the
   data plane. The operator enforces the control plane part of this order
   and waits for you between the stages. (On the lab the first stage is
   empty: see [01](01-openstack-version-and-minor-update.md).)
4. Change one axis at a time and let the platform return to `Ready` before
   touching the next one.

## Mapping from Kolla-Ansible

| Kolla-Ansible | Operator-managed lab | Notes |
|---|---|---|
| Edit `globals.yml` / config overrides, `kolla-ansible reconfigure` | Edit the `OpenStackControlPlane` CR; reconciliation applies it | No command to run; see [operations](../operations/) |
| Bump `openstack_release`, `kolla-ansible pull` + `upgrade` | Operator upgrade (new images become *available*), then `targetVersion` (images are *applied*) | Two separate decisions |
| `kolla-ansible upgrade --limit compute01` | `OpenStackDataPlaneDeployment` with `servicesOverride` and optionally `ansibleLimit` | Each run is a new resource |
| Upgrade the deployment tool itself (`pip install kolla-ansible==...`) | Operator upgrade through OLM | The "tool" runs permanently inside the cluster |
| Host OS upgrade of controllers | OKD upgrade (node OS is part of the OKD release) | Not managed with a package manager |
| Host OS/package update of computes | Data plane deployment with the `update` service | |
| `mariabackup` via `kolla-ansible mariadb_backup` | `GaleraBackup` / `GaleraRestore` resources | [05](05-backup-and-restore.md) |
| Roll back by redeploying the previous tag | No supported downgrade on any axis | [04](04-rollback-limitations.md) |

## Documents

| Document | Phase | Topic | Lab validation |
|---|---|---|---|
| [01-openstack-version-and-minor-update.md](01-openstack-version-and-minor-update.md) | 3 | The `OpenStackVersion` resource and the staged service update | Validated, with a simulated newer version |
| [02-operator-upgrade.md](02-operator-upgrade.md) | 3 | Upgrading the operators through OLM | Partial: no newer bundle was offered |
| [03-failed-upgrade.md](03-failed-upgrade.md) | 3 | Investigating an update that stalls | Partial: no failure provoked |
| [04-rollback-limitations.md](04-rollback-limitations.md) | 3 | What can and cannot be undone | Partial: no restore, no real downgrade |
| [05-backup-and-restore.md](05-backup-and-restore.md) | 3 | State inventory, backups, restore order | Partial: all backups taken, no restore |
| [06-okd-maintenance-impact.md](06-okd-maintenance-impact.md) | 3 | What OKD operations do to OpenStack | Partial: reboot, shutdown and restart done; no MachineConfig change |
| [07-okd-upgrade.md](07-okd-upgrade.md) | 4 | Upgrading OKD itself | Partial: read-only checks only, upgrade not executed |

Values measured on the lab (one OKD node, one compute node):

| Operation | Duration | Effect seen from outside |
|---|---|---|
| Override of one image (Keystone) | about 1 min | Service resource not `Ready` meanwhile; rolling replacement |
| Staged minor update, both planes | about 10 min | Every service restarted once; compute packages updated |
| Database backup job (`GaleraBackup`) | 15 s per instance | None |
| etcd backup | a few seconds | None |
| Planned reboot of the OKD node | about 6 min | All OpenStack APIs down |
| Graceful shutdown, volume snapshots, restart | about 10 min | All OpenStack APIs down |

## Conventions

Command blocks are tagged:

- **[READ-ONLY]** — inspects, never modifies.
- **[CHANGE]** — modifies the platform in a way the platform is designed for.
- **[DESTRUCTIVE]** — can lose data or cause an outage that does not heal by
  itself. Read the risks section first.

Unless stated otherwise, commands run on the bastion, and OpenStack resources
live in the `openstack` namespace:

```bash
oc project openstack
```

Every document ends with what was not tested. A procedure that was not
executed is described from upstream source and documentation and says so.
