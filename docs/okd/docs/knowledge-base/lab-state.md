---
title: "State of the lab after the knowledge base campaigns"
description: "Inventory of the objects the knowledge base campaigns left on the lab, separating baseline from residue, with the command to list and remove each item."
---

# State of the lab after the knowledge base campaigns

> Status: inventory taken on the lab (single-node OKD 4.22, operators
> 18-stable, OpenStack 2023.1 Antelope) on 2026-11-12, after the fourth
> campaign; `tests/smoke-test.sh --functional` reported 0 failed

## In short

- The campaigns reverted their changes but left some objects on purpose:
  data plane deployments kept as history, two database dumps per
  instance, the `kb-demo` tenant, and backups on the bastion.
- Permanent and now part of the baseline: the ConfigMap
  `nova-extra-config` and the catalog image pinned by digest.
- The inventory below is from 2026-11-12 (9 deployments). The drills of
  2026-11-13 added two deployments (11 in total), one backup directory
  on the bastion and a third etcd revision, and nothing else.
- Nothing is close to a limit (`/var` at 32 %); the removal commands are
  there for the habit.

The four campaigns of 2026-11-12 changed the lab and reverted their
changes, but some objects were kept on purpose (history, replay of the
entries) and some are permanent. This file lists every one of them with
the command that shows it and the command that removes it, so that the
next person knows what is baseline and what is residue. Commands run on
the bastion with the `openstack` namespace selected, with the helpers of
the [README](index.md).

## Entries

### What did the campaigns leave on the lab, and how do I list and remove each item?

**Context**: before a demonstration, an upgrade test, or when something
in the lab looks unfamiliar and you wonder whether it belongs to the
documented baseline.

**How**:

**[READ-ONLY]** List everything that is not part of a fresh
installation.

```bash
# 1. data plane deployments kept as history, and their Jobs and pods
oc get openstackdataplanedeployment
oc get jobs -o json | jq -r '.items[] | "\(.metadata.ownerReferences[0].kind) \(.metadata.name)"' | awk '{print $1}' | sort | uniq -c
oc get pods --field-selector=status.phase=Succeeded --no-headers | wc -l
# 2. database dumps on the backup volumes and etcd snapshots
for c in backup-openstack backup-openstack-cell1; do oc get cronjob $c -o jsonpath='{.metadata.name} {.spec.schedule}{"\n"}'; done
oc get pvc | grep -i backup
node 'sudo ls -la /home/core/assets/backup'
ls -la ~/backups
# 3. demo tenant
os domain show kb-demo -c name -c enabled
os project list --domain kb-demo; os user list --domain kb-demo
os network list -c Name; os router list -c Name; os server list --all-projects
os image list -c Name; os flavor list --all -c Name
ls ~/kb-demo
# 4. permanent configuration added by the campaigns
oc get configmap nova-extra-config -o jsonpath='{.data}{"\n"}'
oc get keystoneendpoint placement -o jsonpath='{.metadata.annotations}{"\n"}'
oc -n openstack-operators get catalogsource openstack-operator-index -o jsonpath='{.spec.image}{"\n"}'
# 5. platform residue
oc get pods -A --field-selector=status.phase=Failed
oc get pv | grep -c Available
node 'df -h /var | tail -1; sudo podman system df'
```

**[CHANGE]** Remove, item by item. None of this is needed for the lab to
work; the first two blocks only delete history.

```bash
# 1. old data plane deployments: deleting one deletes its Jobs and pods.
#    Keep the most recent deployment that ran every service (the node set
#    reports its status from it).
oc delete openstackdataplanedeployment kb1-nova-ratio-1 kb1-nova-ratio-2
oc delete openstackdataplanedeployment edpm-scale-out-1 edpm-scale-in-1
#    completed pods of CronJobs disappear with their Jobs (history limits)
# 2. dumps beyond the newest two per instance (run on the node)
node 'sudo sh -c "cd /var/lib/openstack-lab-pv/<pv>/data && ls -1t openstack_backup_2*.sql.gz | tail -n +3 | xargs -r rm -v"'
node 'sudo sh -c "cd /var/lib/openstack-lab-pv/<pv>/data && ls -1t openstack_backup-grants_*.sql.gz | tail -n +3 | xargs -r rm -v"'
node 'sudo sh -c "cd /home/core/assets/backup && ls -1t snapshot_*.db | tail -n +3 | xargs -r rm -v"'
# 3. demo tenant, in dependency order
os router remove subnet kb-demo-router <subnet>; os router unset --external-gateway kb-demo-router; os router delete kb-demo-router
os network delete kb-demo-net kb-public
os image delete kb-cirros-0.6.3; os flavor delete kb.tiny kb.small
os project delete --domain kb-demo kb-demo
os domain set --disable kb-demo; os domain delete kb-demo      # deletes its users
rm -rf ~/kb-demo
# 4. annotation used to wake an operator
oc annotate keystoneendpoint placement kb1/poke-
```

On 2026-11-13 the test with three compute nodes added two deployments
to the history, `edpm-scale-out-2` and `edpm-scale-in-2` (the most
recent one that ran every service: keep it), which makes 11 deployments,
and nothing else: its instances, floating IP and node records were
removed, and the functional smoke test reported 0 failed afterwards.

The etcd restore of the same day left one more backup directory on the
bastion (dumps, exports and the restored snapshot, 127 MB) and a third
etcd revision on the node; its namespace, instance, network, Jobs, the
restore source and `/var/lib/etcd-backup` (560 MB together) were
removed, the dumps pruned to two per instance, and the functional smoke
test reported 0 failed.

**Observed on the lab** (2026-11-12, after the cleanup of the fourth
campaign):

```text
# data plane deployments (9): the initial one, two OVN updates, two service updates,
# scale-out, scale-in, and two from the allocation ratio entry
edpm-deployment edpm-update-ovn-1 edpm-update-ovn-2 edpm-update-services-1 edpm-update-services-2
edpm-scale-out-1 edpm-scale-in-1 kb1-nova-ratio-1 kb1-nova-ratio-2
     51 OpenStackDataPlaneDeployment      # Jobs, no time-to-live
      6 CronJob                           # within the history limits
57                                        # completed pods in the namespace
# backups
backup-openstack @daily / backup-openstack-cell1 @daily
2 dumps and 2 grants files per instance   # 504K and 108K; plus a transfer directory of about 200M each, rewritten by every backup
2 etcd snapshots on the node (234M), 3 copies on the bastion (91M, 209M, 322M)
# demo tenant: domain kb-demo, project kb-demo, two users, networks kb-demo-net and kb-public,
# router kb-demo-router, image kb-cirros-0.6.3, flavors kb.tiny and kb.small, no server, no floating IP
# permanent
nova-extra-config: [libvirt] virt_type = kvm, cpu_mode = host-model, live_migration_inbound_addr = $host
catalog image pinned by digest
# platform
2 failed installer pods from the installation day (kube-controller-manager, kube-scheduler): harmless
3 local volumes Available out of 12
/var: 47G used of 150G (32 %), inodes 1 %; images 33G of which 11G reclaimable
```

Cleanup done by the fourth campaign, with the disk usage of `/var`
before and after:

```text
removed: 16 dump files (8 per instance), the oldest etcd snapshot (89M), 6 manual Jobs and their pods,
         the certificate watcher of the second campaign on the bastion (script and log)
before:  47G used, 103G free, 32 %     completed pods in openstack: 63     Jobs: 63
after:   47G used, 103G free, 32 %     completed pods in openstack: 57     Jobs: 57
```

The cleanup freed about 90 MB: nothing on this lab is close to a limit,
the point of the exercise is the habit and the commands.

**Why / how it works**: three kinds of objects accumulate. Jobs of
data plane deployments have an owner (the deployment) and no
time-to-live, so they live as long as the deployment object. Database
dumps are written by the backup CronJobs to a volume and are never
rotated by the operator on this version. Everything else in the list
was created by hand for an entry and kept so that the entry can be
replayed. The `nova-extra-config` ConfigMap is different: it was created
for live migration during the scale-out, the node set references it, and
removing it would change the configuration of the compute node at the
next deployment; it is now part of the baseline. Kolla-Ansible
equivalent: old container images and `/etc/kolla` backups on each host,
cleaned with `kolla-ansible prune-images` and by hand.

**Pitfalls**:

- Do not delete all data plane deployments: the node set computes its
  `Ready` status and its deployed versions from the deployments that
  still exist.
- The unused container images (11 GB) were left alone: kubelet removes
  them by itself when the disk passes its high threshold, and removing
  them by hand means pulling them again through the proxy at the next
  restart of a pod.
- The backup volumes are local directories on the node disk: their
  "size" is not enforced, so a forgotten retention fills `/var`, which
  etcd shares.
- The `kb-public` network belongs to the demo tenant entries, not to the
  baseline; the smoke test creates and deletes its own networks.
- The dumps, the etcd snapshots and the control-plane exports on the
  bastion contain every secret of the lab. Remove them with the same
  care as you keep them.

**See also**:
[OLM and the OpenStack operators](okd-olm-and-operators.md) (garbage entry),
[Backup and restore drills](backup-and-restore-drills.md),
[OKD storage](okd-storage.md),
[open questions](open-questions.md)
