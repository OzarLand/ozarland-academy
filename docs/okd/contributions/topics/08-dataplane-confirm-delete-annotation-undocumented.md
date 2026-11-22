---
title: "08 — The annotation required to delete a running data plane deployment is not documented"
description: "Contribution proposal documenting the confirm-delete annotation that blocks deleting a running data plane deployment, with lab captures of the effects."
---

# 08 — The annotation required to delete a running data plane deployment is not documented

- **Target:** `openstack-k8s-operators/openstack-operator`, branch `main`
  (documentation under `docs/assemblies/`)
- **Type:** documentation addition
- **Effort:** small (one short section)
- **Status:** candidate, lab evidence complete — refusal, confirmed
  deletion and their effects captured on the lab on 2026-11-14; text
  ready as a diff against `main`; not built with `make docs`
- **Upstream state checked on:** 2026-11-14

## Summary

Since August 2026 an admission webhook refuses to delete an
`OpenStackDataPlaneDeployment` that is still running, unless the object
carries the annotation `dataplane.openstack.org/confirm-delete=true`.
The only places that mention the annotation are the webhook's own error
message, the code and the tests. The documentation does not say that the
protection exists, why, or what deleting a running deployment does to
the Jobs and to the nodes.

## Why it matters in production

- Stopping a deployment that goes wrong (wrong limit, wrong variable) is
  an emergency gesture. The operator discovers the protection at that
  moment, from an error message.
- The message says the nodes may be left "in an inconsistent or
  unrecoverable state" without saying what to check afterwards. A few
  lines on what really happens (the running Job and its pod are removed,
  Ansible stops where it is, the next deployment starts again from the
  first service) would turn fear into a procedure.

## Evidence from the lab

Lab: `openstack-operator.v0.8.0` (18-stable catalog).

- First data plane deployment, 2026-11-11 (validation log, section
  "Data plane"): deleting the failed-in-progress deployment was refused;
  the annotation was needed.
- The lab documents the gesture in its own
  [data plane troubleshooting page](../../docs/troubleshooting/dataplane.md):
  message "deletion of a running deployment not allowed: set annotation
  dataplane.openstack.org/confirm-delete=true to confirm", then
  `oc annotate openstackdataplanedeployment <name> dataplane.openstack.org/confirm-delete=true`
  and the delete.

### Refusal and confirmed deletion on a test deployment (2026-11-14)

Two throw-away `OpenStackDataPlaneService` objects were created for the
exercise, each with an inline playbook: one runs `sleep 150` on the node
(a long, harmless task), the other fails on purpose. Both were removed
afterwards.

Deployment `okdlab-contrib-b` (only the `sleep 150` service), times in
UTC:

| Time | Action | Observation |
| --- | --- | --- |
| 10:08:15 | deployment created | |
| 10:08:55 | state | "Deployment in progress"; one Job `Running`, one pod `Running`; `sleep 150` running on the compute node for 37 s |
| 10:08:55 | `oc delete openstackdataplanedeployment okdlab-contrib-b` | refused, return code 1, messages below; the deployment keeps running |
| 10:08:56 | `oc annotate ... dataplane.openstack.org/confirm-delete=true`, then the same delete | accepted, return code 0 |
| 10:09:01 | state | deployment not found; no Job and no pod with the label `openstackdataplanedeployment=okdlab-contrib-b`; no `sleep 150` process left on the node; pod event "Killing" |
| 10:09:27 | state | same |

Complete output of the refused command:

```text
Warning: Deleting a running OpenStackDataPlaneDeployment may leave nodes in an inconsistent or unrecoverable state. To confirm deletion, set the annotation dataplane.openstack.org/confirm-delete=true and retry.
Error from server (Forbidden): admission webhook "vopenstackdataplanedeployment-v1beta1.kb.io" denied the request: openstackdataplanedeployments.dataplane.openstack.org "okdlab-contrib-b" is forbidden: deletion of a running deployment not allowed: set annotation dataplane.openstack.org/confirm-delete=true to confirm
```

So, on this version: the Job and its pod disappear with the deployment
within 5 seconds, and the task that Ansible was running on the node is
interrupted within the same 5 seconds (the process started by the task
was gone).

Deployment `okdlab-contrib-a` (the `sleep 150` service, then the failing
one, `backoffLimit: 1`), once in error ("Deployment error occurred in
okdlab-fail service ... backoff limit reached"): deleted at 10:11 with a
plain `oc delete`, no annotation, return code 0. This answers the first
open question below: the protection applies only while the deployment is
in progress.

NodeSet `openstack-edpm` after the two deletions: `Ready` True "NodeSet
Ready", `DeploymentReady` True "Deployment completed". Between the two
deletions it showed the error of `okdlab-contrib-a`; deleting the
interrupted deployment left no trace in its conditions.

**Not verified on the lab:**

- The interrupted task was a `sleep`. What an interrupted real service
  (for example a package installation or a container restart) leaves on
  a node was not studied; the proposed text only says to check the
  nodes.
- No new deployment was run after the deletion on 2026-11-14. The only
  observation of that kind is from 2026-11-11: after such a deletion,
  the next full deployment succeeded.
- "Services that had already completed are not rolled back" in the
  proposed text comes from how the deployment works (one Job per
  service, nothing that undoes a Job); the test deployment that was
  interrupted had a single service.
- The page was not built: `make docs` needs tooling that is not
  installed on the workstation used here.

## Upstream state

Looked at on 2026-11-13 (`main` at
`1a58205d24a6e9aeac5a2de15a302ea597b2c9eb`) and again on 2026-11-14
(`main` at `85bcf368e833d5d8c4246d3e5a8e9d3c911d008e`, commit of
2026-11-13 17:34 UTC): same facts, same line numbers in the webhook
file, and the troubleshooting page is unchanged since `1a58205`.

| Fact | Pointer |
| --- | --- |
| Webhook refuses the deletion while the `DeploymentReady` condition has the reason "Requested", unless the annotation is `true` | [`api/dataplane/v1beta1/openstackdataplanedeployment_webhook.go` L117-L136](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/api/dataplane/v1beta1/openstackdataplanedeployment_webhook.go#L117-L136) |
| Annotation constant | `api/dataplane/v1beta1/const.go` L23-L25 |
| Introduced by | pull request #2013 "Require confirm-delete annotation for OpenStackDataPlaneDeployment deletion", merged 2026-08-05; `18-stable` copy #2059. The file list of #2013 has code, manifests and tests, no file under `docs/` |
| No mention in the documentation | `grep -rn confirm-delete docs/` on the commit above: no match |

Duplicate search on 2026-11-13 in the same repository (issues and pull
requests, open and closed): "confirm-delete" (10 results: #2013, #2059
and dependency bumps), "deletion of a running deployment" (17 results,
none about documentation). No open documentation pull request.

Repeated on 2026-11-14 with the search API (`repo:openstack-k8s-operators/openstack-operator <words>`,
issues and pull requests, open and closed): "confirm-delete"
(11 results: #2013, #2059, dependency bumps and unrelated pull
requests), "deletion of a running deployment" (17), "confirm-delete
docs" (2: #2013 and an unrelated annotation), "delete running deployment
documentation" (14). Nothing proposes to document the annotation.

**Not specific to the lab.**

## Proposed contribution

One pull request against `main` adding a short block at the end of
`docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc`.
[Topic 07](07-dataplane-troubleshooting-doc-removed-resource.md) rewrites
the middle of the same page; this block is appended after the last line,
so the two diffs do not overlap, but sending them one after the other
keeps the review simple.

Diff against `main` at `85bcf368e833d5d8c4246d3e5a8e9d3c911d008e`
(checked with `git apply --check` on that commit; the page uses block
titles such as `.Check service pod status reports`, the new block
follows the same form):

```diff
diff --git a/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc b/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc
index 161efcc..5da74c2 100644
--- a/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc
+++ b/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc
@@ -79,3 +79,24 @@ This allows selection and monitoring of these pods using CLI commands.
 When encountering failures within OpenStackAnsibleEE jobs, the resulting Kubernetes Pod reports will be formatted with an error message in the following manner: `openstackansibleee job <POD_NAME> failed due to <ERROR> with message: <ERROR_MSG>`.
 
 These reports can provide valuable insights into the cause of the failure and aid in resolving related issues.
+
+.Deleting a deployment that is still running
+
+An admission webhook refuses to delete an `OpenStackDataPlaneDeployment` while the deployment is in progress, because interrupting Ansible in the middle of a service can leave the nodes in an inconsistent state:
+
+----
+$ oc delete openstackdataplanedeployment <deployment_name>
+Warning: Deleting a running OpenStackDataPlaneDeployment may leave nodes in an inconsistent or unrecoverable state. To confirm deletion, set the annotation dataplane.openstack.org/confirm-delete=true and retry.
+Error from server (Forbidden): admission webhook "vopenstackdataplanedeployment-v1beta1.kb.io" denied the request: openstackdataplanedeployments.dataplane.openstack.org "<deployment_name>" is forbidden: deletion of a running deployment not allowed: set annotation dataplane.openstack.org/confirm-delete=true to confirm
+----
+
+If you need to stop the deployment, for example because it was started with a wrong service list or a wrong limit, confirm the deletion with the annotation and delete the resource again:
+
+----
+$ oc annotate openstackdataplanedeployment <deployment_name> dataplane.openstack.org/confirm-delete=true
+$ oc delete openstackdataplanedeployment <deployment_name>
+----
+
+The Job of the service that was being executed and its pod are deleted with the deployment, and the Ansible task that was running on the nodes is interrupted. Services that had already completed are not rolled back. Check the state of the nodes before you create a new `OpenStackDataPlaneDeployment`.
+
+A deployment that has completed or failed is deleted without the annotation.
```

Every sentence of the block is backed by the run above, except the two
points listed under "Not verified".

## Reproduction and validation plan

1. Done 2026-11-14. `[CHANGE]` Start a deployment limited to a harmless
   service on the lab, try `oc delete` while it runs, capture the
   refusal.
2. Done 2026-11-14. `[CHANGE]` Annotate, delete, and record: what
   happens to the Job and its pod, the Ansible task that ran on the
   node, the NodeSet conditions afterwards.
3. Not done on 2026-11-14 (done once on 2026-11-11). `[CHANGE]` Run a
   normal deployment, confirm the NodeSet returns to Ready.
4. Not done. Build with `make docs` and read the rendered page.

## Effort and risk

- Two hours on the lab, one hour of writing.
- Risk: describing consequences beyond what was tested. Keep to the
  observed behaviour and say on which version.

## Review-readiness checklist

- [x] Refusal and deletion captured on the lab (steps 1 and 2)
- [x] Text limited to verified behaviour (two sentences flagged above)
- [ ] Placement of the section agreed (ask in the description)
- [ ] `make docs` builds
- [ ] Commit with `Signed-off-by`

## Open questions

- Answered on 2026-11-14: the protection does not apply to a deployment
  in error; it was deleted without the annotation, as the code says.
- Does the author of #2013 prefer the explanation in the API reference
  (generated from Go comments) instead of a procedure page?

## Draft pull request text

> **Title:** docs: document the confirm-delete annotation for running
> data plane deployments
>
> \#2013 added a webhook check that refuses to delete a running
> `OpenStackDataPlaneDeployment` unless it is annotated with
> `dataplane.openstack.org/confirm-delete=true`. The documentation does
> not mention it, so users meet it for the first time in an error
> message.
>
> This adds a short block at the end of the data plane troubleshooting
> page with the message, the two commands and what to expect afterwards.
> Behaviour described as observed on an 18-stable deployment
> (openstack-operator 0.8.0, OKD 4.22): the running Job and its pod were
> gone within seconds, the task running on the node was interrupted, and
> a failed deployment was deleted without the annotation.
>
> Happy to move the text to another page if you prefer.
