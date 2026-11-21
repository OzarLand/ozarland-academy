---
title: "09 — Scale-in documentation: the follow-up deployment, the second agent and the leftovers are missing"
description: "The upstream procedure to remove a compute node from a NodeSet stops at the patch that removes the node from the spec."
---

# 09 — Scale-in documentation: the follow-up deployment, the second agent and the leftovers are missing

- **Target:** `openstack-k8s-operators/openstack-operator`, branch `main`
  (`docs/assemblies/dataplane_scaling_out.adoc`, section "Scaling In")
- **Type:** documentation improvement
- **Effort:** small to medium (three additions, each backed by a lab run)
- **Status:** candidate — the procedure was run twice on the lab (one
  node, then two nodes at once); the gaps were read on `main`
- **Upstream state checked on:** 2026-11-13

## Summary

The upstream procedure to remove a compute node from a NodeSet stops at
the patch that removes the node from the spec. Three things an operator
needs are not there:

1. **A new deployment is needed afterwards.** The page only says so for
   the removal of a whole NodeSet. For a single node, the remaining nodes
   keep the removed host in `/etc/ssh/ssh_known_hosts` until a deployment
   runs, and the certificate cleanup of the operator only runs during a
   deployment.
2. **The node has more than one network agent.** The example deletes one
   "OVN Controller agent". A compute node deployed with the default
   services also has an "OVN Metadata agent" record, which stays dead in
   the list if it is not deleted.
3. **What the operator does not do.** Nothing runs on the removed node:
   containers, Open vSwitch bridges, configuration, SSH key and
   certificates stay on it. For a pre-provisioned node that is reused,
   this matters. And until
   [topic 03](03-nodeset-stale-certificates-after-scale-in.md) is fixed,
   the `Certificate` objects of the node may have to be deleted by hand.

## Why it matters in production

- Decommissioning is rare, so it is done from the documentation, step by
  step. A missing step is a missing action.
- Dead agent records and stale known-hosts entries are the kind of
  residue that surfaces months later as a confusing alert or a refused
  migration.
- A pre-provisioned node handed back to another team with the Nova SSH
  key and valid certificates still on disk is a security finding.

## Evidence from the lab

Lab: 18-stable operators, pre-provisioned CentOS Stream 9 nodes; runs of
2026-11-12 (two nodes to one) and 2026-11-13 (three nodes to one),
recorded in the knowledge base entries
[how do I remove a compute node cleanly](../../docs/knowledge-base/dataplane-scale-out-and-migration.md#how-do-i-remove-a-compute-node-cleanly)
and
[what does the operator do when a node leaves the NodeSet](../../docs/knowledge-base/dataplane-scale-out-and-migration.md#what-does-the-operator-do-when-a-node-leaves-the-nodeset):

- Both agents of the node were deleted (`network agent list --host`
  returned two records); the chassis and its private record left the
  southbound database within seconds.
- Deleting the compute service removed the resource provider, the
  hypervisor and the host mapping.
- The removed node stayed in `/etc/ssh/ssh_known_hosts` of the remaining
  node until the next deployment; after it, it was gone.
- Nothing ran on the removed node; its containers, bridges,
  configuration under `/var/lib/openstack`, SSH key and certificates
  were still there.
- The follow-up deployment took 13 to 14 minutes on the remaining node
  and restarted `nova_compute`.

**Not verified on the lab:**

- Bare-metal provisioned nodes (the page says they are de-provisioned);
  the lab only has pre-provisioned ones.
- Whether a deployment limited to the `ssh-known-hosts` service is enough
  after a removal; the lab ran full deployments.
- A deployment without the metadata agent (`neutron-ovn` service
  instead): the agent list may differ.

## Upstream state

Looked at on 2026-11-13, `main` at `1a58205d24a6e9aeac5a2de15a302ea597b2c9eb`.

| Fact | Pointer |
| --- | --- |
| "Scaling In" ends with the patch of the NodeSet; no deployment step | [`docs/assemblies/dataplane_scaling_out.adoc` L121-L226](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/docs/assemblies/dataplane_scaling_out.adoc#L121-L226) |
| The new deployment is only mentioned for the removal of a whole NodeSet, for the SSH host keys | same file, L228-L239 |
| Agent example shows and deletes only "OVN Controller agent" | same file, L164-L184 |
| Certificate cleanup runs from the deployment controller | see the pointer table of topic 03 |
| Last change of the page | commit `2ad63fdf72`, 2026-01-15 (GitHub commit list for the path) |

Duplicate search on 2026-11-13 in the same repository (issues and pull
requests, open and closed): "scale in", "removing a node nodeset docs":
nothing about this page. The Jira project could not be searched.

**Not specific to the lab**, except that the lab cannot speak for
bare-metal provisioning.

## Proposed contribution

One pull request against `main`, three small additions to the existing
section, in the page's own style:

1. after the patch: "create a new `OpenStackDataPlaneDeployment` for the
   NodeSet", with the reason (known hosts, certificates);
2. in "Delete network agents": list by host and delete every agent of
   the node;
3. a short note "what remains on the removed node" for pre-provisioned
   nodes.

Do not mention the certificate bug in the documentation; it belongs to
topic 03.

## Reproduction and validation plan

The lab runs already cover the facts. Before sending:

1. `[CHANGE]` One more scale-out and scale-in on the lab, following the
   **upstream** page to the letter first, noting each point where it is
   not enough.
2. `[CHANGE]` Try the follow-up deployment with
   `servicesOverride: [ssh-known-hosts]` only, to know whether the short
   form can be recommended.
3. Build with `make docs`.

## Effort and risk

- One lab cycle (about an hour) and the writing.
- Risk: low. Keep each addition short; a reviewer who knows the bare-metal
  path may ask for wording that covers both cases.

## Review-readiness checklist

- [ ] Upstream page followed literally once, gaps noted
- [ ] Short-form deployment tested or not recommended
- [ ] Wording checked against the bare-metal paragraph
- [ ] `make docs` builds
- [ ] Commit with `Signed-off-by`

## Open questions

- Should the cleanup of the node itself be a documented manual step, or
  is the `cleanup` service (described in `con_data-plane-services.adoc`
  for removed services) meant to cover a removed node one day?
- Would the maintainers rather see the three additions as three pull
  requests?

## Draft pull request text

> **Title:** docs: complete the scale-in procedure for a single node
>
> Three additions to "Scaling In", from two runs on an 18-stable
> deployment with pre-provisioned nodes:
>
> - a new deployment is needed after removing a node from a NodeSet (the
>   page only said so for the removal of a whole NodeSet); until then the
>   remaining nodes keep the removed host in their known hosts;
> - a compute node has an OVN metadata agent record as well as the
>   controller one; list agents by host and delete all of them;
> - nothing is cleaned on a removed pre-provisioned node; say so.
