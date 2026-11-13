# 08 — The annotation required to delete a running data plane deployment is not documented

- **Target:** `openstack-k8s-operators/openstack-operator`, branch `main`
  (documentation under `docs/assemblies/`)
- **Type:** documentation addition
- **Effort:** small (one short section)
- **Status:** candidate, high confidence — refusal observed on the lab;
  the feature and the absence of documentation were read on `main`
- **Upstream state checked on:** 2026-11-13

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

**Not verified on the lab:**

- What exactly remains on a node when the deployment is deleted in the
  middle of a service was not studied; only "the next full deployment
  succeeded" is known.

## Upstream state

Looked at on 2026-11-13, `main` at `1a58205d24a6e9aeac5a2de15a302ea597b2c9eb`.

| Fact | Pointer |
| --- | --- |
| Webhook refuses the deletion while the Ready condition has the reason "Requested", unless the annotation is `true` | [`api/dataplane/v1beta1/openstackdataplanedeployment_webhook.go` L117-L136](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/api/dataplane/v1beta1/openstackdataplanedeployment_webhook.go#L117-L136) |
| Annotation constant | `api/dataplane/v1beta1/const.go` L23-L25 |
| Introduced by | pull request #2013 "Require confirm-delete annotation for OpenStackDataPlaneDeployment deletion", merged 2026-08-05; `18-stable` copy #2059. The file list of #2013 has code, manifests and tests, no file under `docs/` |
| No mention in the documentation | `grep -rn confirm-delete docs/` on the commit above: no match |

Duplicate search on 2026-11-13 in the same repository (issues and pull
requests, open and closed): "confirm-delete" (10 results: #2013, #2059
and dependency bumps), "deletion of a running deployment" (17 results,
none about documentation). No open documentation pull request.

**Not specific to the lab.**

## Proposed contribution

One pull request against `main` adding a short section, most likely at
the end of `proc_troubleshooting-data-plane-creation-and-deployment.adoc`
(after [topic 07](07-dataplane-troubleshooting-doc-removed-resource.md)
is merged, to avoid two changes of the same page in review at once) or
in `proc_deploying-the-data-plane.adoc`:

- when the deletion is refused and the exact message;
- the two commands (annotate, delete);
- what the deletion does, stated only as far as it was verified;
- what to run next (a new deployment).

## Reproduction and validation plan

1. `[CHANGE]` Start a deployment limited to a harmless service on the
   lab, try `oc delete` while it runs, capture the refusal.
2. `[CHANGE]` Annotate, delete, and record: what happens to the Job and
   its pod, the last Ansible task that ran on the node, the NodeSet
   conditions afterwards.
3. `[CHANGE]` Run a normal deployment, confirm the NodeSet returns to
   Ready.
4. Build with `make docs`.

## Effort and risk

- Two hours on the lab, one hour of writing.
- Risk: describing consequences beyond what was tested. Keep to the
  observed behaviour and say on which version.

## Review-readiness checklist

- [ ] Refusal and deletion captured on the lab (steps 1 and 2)
- [ ] Text limited to verified behaviour
- [ ] Placement of the section agreed (ask in the description)
- [ ] `make docs` builds
- [ ] Commit with `Signed-off-by`

## Open questions

- Is the protection also meant for deployments in error (reason other
  than "Requested")? The code says no; say it in the text only after a
  test.
- Does the author of #2013 prefer the explanation in the API reference
  (generated from Go comments) instead of a procedure page?

## Draft pull request text

> **Title:** docs: document the confirm-delete annotation for running
> data plane deployments
>
> #2013 added a webhook check that refuses to delete a running
> `OpenStackDataPlaneDeployment` unless it is annotated with
> `dataplane.openstack.org/confirm-delete=true`. The documentation does
> not mention it, so users meet it for the first time in an error
> message.
>
> This adds a short section with the message, the two commands and what
> to expect afterwards. Behaviour described as observed on an 18-stable
> deployment (OKD 4.22).
