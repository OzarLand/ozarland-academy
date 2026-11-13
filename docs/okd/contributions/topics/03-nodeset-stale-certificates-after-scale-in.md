# 03 — Certificates of a removed data plane node are not cleaned up when the NodeSet returns to an earlier spec

- **Target:** `openstack-k8s-operators/openstack-operator`, branch `main`
  (then backport to `18-stable`)
- **Type:** bug fix (Go, data plane controllers) + functional test
- **Effort:** medium (small code change, but the test needs two
  deployments and a design choice the maintainers must agree with)
- **Status:** candidate — leftovers observed twice on the lab at
  18-stable; cause read in the code and consistent with the hashes stored
  on the lab; the skipped code path itself was not observed (no log left)
- **Upstream state checked on:** 2026-11-13

## Summary

Since February 2026 the operator deletes the `Certificate` objects and
Secrets of a node that was removed from an `OpenStackDataPlaneNodeSet`.
The cleanup only runs when the NodeSet has a configuration that is not
deployed yet (`status.configHash != status.deployedConfigHash`).

The NodeSet controller, however, walks through **all** the deployments
that reference the NodeSet, old ones included, and copies the hash of
any `Ready` deployment whose stored hash equals the current one into
`status.deployedConfigHash`. When a scale-in brings the NodeSet spec back
to a spec that was deployed before (remove the node that was added last
week), an old deployment matches at once, the two hashes are equal
before the new deployment starts, and the cleanup is skipped. The
certificates of the removed node, with their private keys, stay in the
namespace and cert-manager keeps renewing them.

## Why it matters in production

- Scale-out followed by scale-in of the same node is the ordinary life of
  a compute fleet: hardware replacement, a node lent for a test, a failed
  addition that is rolled back. It is exactly the case where the spec
  returns to an earlier value.
- What is left behind is key material: valid TLS certificates and keys
  for libvirt, OVN and the metadata agent in the name of a host that no
  longer exists, signed by the internal CA and renewed for ever.
- An operator who trusts the cleanup added upstream will not look for
  them. The lab only saw them because it lists everything after a drill.
- The same stale `deployedConfigHash` may have other effects (see open
  questions); the certificates are the visible one.

## Evidence from the lab

Lab: `openstack-operator.v0.8.0` from the 18-stable catalog, bundle
created on 2026-11-09 (`createdAt` of the ClusterServiceVersion, read on
2026-11-13), so later than the cleanup commit on `18-stable`
(2026-02-05).

- Scale-in from two nodes to one on 2026-11-12, and from three to one on
  2026-11-13: after the full deployment on the remaining node, the
  `Certificate` objects of the removed nodes and their Secrets were still
  there and were deleted by hand. Recorded in
  [the knowledge base](../../docs/knowledge-base/dataplane-scale-out-and-migration.md).
- Hashes stored by the deployments (`status.nodeSetHashes`, read on
  2026-11-13, shortened here):

  | Deployment | Ready since | NodeSet hash |
  | --- | --- | --- |
  | `edpm-deployment` (first, one node) | 2026-11-11 21:15 | `n57dhb7h…` |
  | `edpm-scale-out-1` (two nodes) | 2026-11-12 17:34 | `n5b6h66h…` |
  | `edpm-scale-in-1` (one node) | 2026-11-12 18:31 | `n57dhb7h…` |
  | `edpm-scale-out-2` (three nodes) | 2026-11-12 21:28 | `n545h5d6…` |
  | `edpm-scale-in-2` (one node) | 2026-11-13 05:41 | `n57dhb7h…` |

  Both scale-in operations returned to the hash of the first deployment,
  which was still present and `Ready`. This is the precondition of the
  mechanism described above.

- `status.secretHashes` of the NodeSet, read on 2026-11-13 after the
  last scale-in and the manual deletion, still lists
  `cert-libvirt-default-edpm-compute-1`, `-2` and the matching `ovn` and
  `neutron-metadata` entries. Pull request #1849 ("Fix stale SecretHashes
  on nodeset status after node removal") resets this map on a full
  deployment; the entries are probably back because the Secrets still
  existed when the scale-in deployment computed its hashes. A second
  visible effect of the same cause.

**Not verified on the lab:**

- The value of `status.deployedConfigHash` between the spec change and
  the scale-in deployment was not read, and the operator log of that
  period is gone (the pod restarted on 2026-11-13). The explanation is a
  code reading that fits the facts, not an observation.
- The counter-test (scale-in to a spec that was never deployed, where the
  cleanup should work) was not done.
- Not tried against a build of `main`.

## Upstream state

Looked at on 2026-11-13, `main` at `1a58205d24a6e9aeac5a2de15a302ea597b2c9eb`,
`18-stable` at `fdd663b50abe1c7b80456fc3175374021c67a730`.

| Fact | Pointer |
| --- | --- |
| Cleanup guarded by the hash comparison | [`internal/dataplane/cert.go` L90-L94](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/internal/dataplane/cert.go#L90-L94); same on `18-stable` |
| Cleanup itself (list by NodeSet, service and key labels, delete when the hostname is unknown) | same file, `cleanupStaleCertificates`, L305-L353 |
| Introduced by | pull request #1792 "Cleanup orphan certificates when nodes are removed from NodeSet", merged 2026-02-03; on `18-stable` as commit `966d0373fa` (2026-02-05) |
| `status.configHash` set when the spec hash differs from the deployed one; the hash covers the whole spec | [`openstackdataplanenodeset_controller.go` L237-L245](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/internal/controller/dataplane/openstackdataplanenodeset_controller.go#L237-L245) and `GetSpecConfigHash`, L997-L1003 |
| Loop over all relevant deployments; a `Ready` deployment whose stored hash equals the current one sets `status.deployedConfigHash` | same file, L560-L659 (comparison at L608, assignment at L659) |
| Only the overall ready/running/failed flags are reset for each deployment, not the hash | same file, L588-L591 |
| The cleanup is called from the deployment controller, once per service certificate | [`openstackdataplanedeployment_controller.go` L239-L240](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/internal/controller/dataplane/openstackdataplanedeployment_controller.go#L239-L240) |

Duplicate search on 2026-11-13 (issues and pull requests, open and
closed, in `openstack-k8s-operators/openstack-operator`): "stale
certificate" (15 results, only #1792 relevant), "orphan certificates"
(#1792), "DeployedConfigHash" (#1990, about certificate Secret changes,
not this), "cleanupStaleCertificates" (#1792). No report of the cleanup
being skipped. The project tracks bugs in Jira (project OSPRH), which
cannot be searched without an account: **a Jira duplicate cannot be
excluded.**

**Not specific to the lab:** nothing in the mechanism depends on the
platform; it needs TLS enabled on the NodeSet (the default in the
reference deployments), an older `Ready` deployment kept in the
namespace, and a spec that returns to the one that deployment applied.

## Proposed contribution

Start with an **issue** (or the Jira bug, see the methodology) with the
reproduction below, because there are two reasonable fixes and the
choice belongs to the maintainers:

1. Run `cleanupStaleCertificates` on every deployment reconcile that
   reaches the TLS step, without the hash guard. The function only lists
   by label and compares hostnames; the guard looks like an optimisation.
2. Keep the guard and stop the NodeSet controller from taking
   `deployedConfigHash` from a deployment that is not the latest one.
   This is the more correct fix, with a wider blast radius.

Then a pull request with the option chosen and a functional test:
NodeSet with one node deployed, add a node and deploy, remove it and
deploy, expect the certificate and Secret of the removed node to be gone.

## Reproduction and validation plan

1. `[READ-ONLY]` Before anything, on a NodeSet with TLS:
   `oc get certificate,secret -n openstack -l osdpns=<nodeset>`
   and `oc get osdpns <nodeset> -o jsonpath='{.status.configHash} {.status.deployedConfigHash}'`.
2. `[CHANGE]` Add a second node to the NodeSet, create a deployment, wait
   for `Ready`. Keep the first deployment object.
3. `[CHANGE]` Remove the second node from the spec (after the Nova and
   OVN clean-up of the knowledge base entry). **Before** creating the
   deployment, read the two hashes again: the expected faulty state is
   "equal".
4. `[CHANGE]` Create the scale-in deployment, wait for `Ready`.
5. `[READ-ONLY]` List certificates and Secrets with the label
   `hostname=<removed node>`: present means reproduced. Search the
   operator log for `Deleting stale certificate`: absent means the
   cleanup did not run.
6. `[CHANGE]` Counter-test: repeat after deleting the old deployments
   whose hash equals the one-node spec (or with a spec that differs by an
   harmless field); the cleanup is expected to run.
7. With a patched operator image (built with `make docker-build` in a
   personal registry), repeat steps 2 to 5.

## Effort and risk

- Code: a few lines for option 1; option 2 touches the status logic that
  several recent fixes changed (#1781, #1849, #1990) and needs care.
- Test: the functional test suite of the repository (envtest, Ginkgo)
  already simulates deployments; a second deployment in the same test is
  the main work.
- Risk for the reputation: low if the issue comes first with the hashes
  and the reproduction; high if a pull request changes the status logic
  without discussion.

## Review-readiness checklist

- [ ] Reproduced on the lab with step 3 showing equal hashes
- [ ] Counter-test done (step 6)
- [ ] Reproduced or code-checked again on current `main`
- [ ] Issue or Jira bug accepted, fix option chosen by a maintainer
- [ ] Functional test fails without the change
- [ ] `make test` and `make golangci-lint` pass locally
- [ ] Commit with `Signed-off-by`, pull request against `main`

## Open questions

- Does a stale `deployedConfigHash` have other consequences, for example
  a NodeSet reported as deployed after a change was reverted without a
  new deployment? The ready flag is reset per deployment, the hash is
  not; to be read carefully before the issue is written.
- Is keeping old deployment objects the expected practice? If the
  documentation asks to delete them, the bug is less likely in
  production and the issue should say so.
- Does the existing test of #1792 cover a second deployment? A search for
  "stale cert" under `test/` found nothing on 2026-11-13; the test was
  not located.

## Draft issue text

> **Title:** Certificates of a removed node are not cleaned up when the
> NodeSet spec returns to a previously deployed one
>
> **Version:** openstack-operator 18-stable (bundle of 2026-11-09), OKD
> 4.22. Code read on `main` at `1a58205d`: same logic.
>
> **What happened:** after removing a node from an
> `OpenStackDataPlaneNodeSet` and running a full deployment, the
> `Certificate` objects and Secrets of the removed node (libvirt, ovn,
> neutron-metadata) were still present. Seen twice.
>
> **What I expected:** the cleanup added by #1792 deletes them.
>
> **Analysis:** `EnsureTLSCerts` only calls `cleanupStaleCertificates`
> when `status.configHash != status.deployedConfigHash`. In my case the
> scale-in returned the NodeSet to the spec of an earlier deployment that
> was still present and Ready. The NodeSet controller loops over all
> relevant deployments and sets `deployedConfigHash` from any Ready
> deployment whose stored hash matches, so the two hashes were already
> equal when the scale-in deployment started. The stored
> `nodeSetHashes` of my deployments show the same hash for the initial
> deployment and for both scale-in deployments.
>
> **How to reproduce:** (steps 2 to 5 above, with outputs)
>
> **Possible fixes:** run the cleanup without the hash guard, or only
> take `deployedConfigHash` from the latest deployment. I can send a pull
> request with a functional test for the option you prefer.
