---
title: "Step 6 — OpenStack data plane"
description: "Installation step 6 configures the compute nodes with Ansible through a service, a node set and an immutable deployment resource, then verifies the result."
---

# Step 6 — OpenStack data plane

**Where:** bastion. **Command:** `scripts/bastion/07-openstack-dataplane.sh`

Skip this step for a control-plane-only lab (`compute_count = 0`).

## In short

- Compute nodes are not Kubernetes nodes: the operator configures them
  with Ansible over SSH, and the services run there as podman containers.
- Three resources: services (the plays), a NodeSet (inventory and
  variables) and a deployment (one run).
- A deployment is immutable. To apply a change or retry, run the script
  again with a **new** deployment name.
- The first deployment took 21 minutes on the lab.

## What we deploy

On each compute VM: OVN controller, the OVN metadata agent, libvirt and
nova-compute, running as containers managed by systemd and podman — much
like a Kolla-Ansible compute host, and unlike the control plane, **not** as
Kubernetes pods.

The operator does this by running Ansible. The playbooks and roles come
from the upstream `edpm-ansible` project and run inside short-lived pods.

## The resources involved

| Resource | Role | Analogy |
|---|---|---|
| `OpenStackDataPlaneService` | A named Ansible play (`bootstrap`, `configure-network`, `ovn`, `nova`, ...) | a role / a tag |
| `OpenStackDataPlaneNodeSet` | A group of nodes, their variables and the ordered list of services | inventory group + group_vars |
| `OpenStackDataPlaneDeployment` | One execution of the node set's services | one `kolla-ansible deploy` run |

A deployment is immutable: once finished it is a record of what ran. To
apply a change, or to retry after a failure, create a **new** deployment
(the script takes the name as argument).

## What the script does

1. Checks SSH access to the nodes with the data plane key.
2. Creates three Secrets: the Ansible SSH key, a key pair for nova live
   migration and the libvirt password.
3. Chooses the hypervisor type and writes the `nova-extra-config`
   ConfigMap. With `COMPUTE_VIRT_TYPE=auto` it checks the CPU flags of the
   first node: `virt_type = qemu` without hardware virtualization, `kvm`
   (the default) with it. The same ConfigMap sets
   `live_migration_inbound_addr`, needed for live migration between two
   nodes.
4. Applies the custom `repo-setup` service and the NodeSet
   (`deployment/openstack/dataplane/`).
5. Creates the deployment and waits. One pod per service runs in sequence.
6. Runs nova cell discovery so the new hypervisors are mapped to cell1.
   Nothing else does it for a node added later.

The first deployment took 21 minutes on the lab; the longest services were
`bootstrap`, `download-cache` and `libvirt` (three to five minutes each).

Adding a second node later (`compute_count = 2`, then the script with a
new deployment name) took the same 21 minutes and did not disturb the
instances of the first node. Going to three nodes and back to one was also
done on the lab. Both are recorded in
[Data plane scale-out, migration and scale-in](../knowledge-base/dataplane-scale-out-and-migration.md).

Running the script again with the same deployment name only waits for that
deployment and changes nothing on the nodes.

Follow the Ansible runs from a second terminal:

**[READ-ONLY]**

```bash
oc -n openstack get pods -l app=openstackansibleee -w
oc -n openstack logs -f <one of these pods>
```

## Concepts worth understanding here

- **Pre-provisioned nodes.** The node set says `preProvisioned: true`: the
  VM and its OS already exist, the operator only needs SSH. The node set
  also declares each node's address on each network; the operator reserves
  them (`oc -n openstack get ipset`) and publishes DNS records for them.
- **Host networking is rewritten.** The `configure-network` service applies
  the NIC template embedded in the node set: the first NIC moves into the
  OVS bridge `br-ex` and keeps the ctlplane address; the other NICs get
  their internalapi and tenant addresses. An error in this template can cut
  the node off the network — the console of the VM is then the only way in.
- **Why the control plane must be reachable on real networks.** After this
  step, `nova-compute` talks to RabbitMQ on its internalapi address and
  `ovn-controller` to the OVN southbound database pod. This is the reason
  for MetalLB, the network attachments and the disabled port security.

## Verify

**[READ-ONLY]**

```bash
oc -n openstack get openstackdataplanenodeset,openstackdataplanedeployment
oc -n openstack rsh openstackclient openstack compute service list
oc -n openstack rsh openstackclient openstack network agent list
oc -n openstack rsh openstackclient openstack hypervisor list
```

Expected: node set `True` ("NodeSet Ready") and deployment `True` ("Setup
complete"); one `nova-compute` service `up` per node; an `OVN Controller
Gateway agent` and an `OVN Metadata agent` alive per node.

On the node itself (from the bastion):

**[READ-ONLY]**

```bash
ssh -i .work/dataplane-ssh-key cloud-admin@<compute ctlplane ip> \
  'sudo podman ps --format "{{.Names}}\t{{.Status}}"; systemctl list-units "edpm_*" --no-pager'
```

Expected: the containers `ovn_controller`, `ovn_metadata_agent` and
`nova_compute`, and the units `edpm_ovn_controller`,
`edpm_ovn_metadata_agent`, `edpm_nova_compute` and `edpm_libvirt.target`.

## If something fails

See [../troubleshooting/dataplane.md](../troubleshooting/dataplane.md). In
short: find the failed job pod, read its Ansible output, fix the cause, and
run the script again with a new deployment name:

**[CHANGE]**

```bash
scripts/bastion/07-openstack-dataplane.sh edpm-deployment-2
```

---

**Previous:** [Step 5 — OpenStack control plane](05-openstack-control-plane.md) · **Next:** [Step 7 — Verification](07-verification.md)
