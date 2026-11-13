# 07 — The data plane troubleshooting page still uses a resource that was removed in 2024

- **Target:** `openstack-k8s-operators/openstack-operator`, branch `main`
  (documentation under `docs/assemblies/`)
- **Type:** documentation fix
- **Effort:** small (one AsciiDoc page, commands and sample outputs to
  replace with ones captured on the lab)
- **Status:** candidate, high confidence — the page was read on `main`,
  the resource it uses does not exist on the lab, the removal is traced
  to a pull request
- **Upstream state checked on:** 2026-11-13

## Summary

The page "Troubleshooting data plane creation and deployment" tells the
reader to run `oc get openstackansibleee` to see the state of each
service of a deployment, and `oc logs job/repo-setup-openstack-edpm` to
read its log. The `OpenStackAnsibleEE` custom resource was replaced by
plain Kubernetes Jobs in July 2024 (pull request #972, closed
2024-07-25). Since then the first command answers "the server doesn't
have a resource type", and Job names include the deployment name, so the
second does not match either. The page has not been touched since it was
added in June 2024.

## Why it matters in production

- It is the page an operator opens when a deployment is stuck, usually
  for the first time and under pressure. Its first diagnostic command
  fails.
- The replacement is not obvious to someone new to the operators: Jobs
  with four labels, and conditions reported in the deployment and NodeSet
  status.
- For a contributor, it is the ideal first pull request: no behaviour
  change, easy to review, and it shows the lab is really used.

## Evidence from the lab

Lab: `openstack-operator.v0.8.0` (18-stable catalog), read on 2026-11-13.

- `oc api-resources | grep -i ansible` lists only `ansibletests`
  (`test.openstack.org`); there is no `openstackansibleee` resource.
- Jobs of a deployment and their labels:

  ```text
  bootstrap-edpm-scale-in-2-openstack-edpm           Complete  1/1  app=openstackansibleee,openstackdataplanedeployment=edpm-scale-in-2,openstackdataplanenodeset=openstack-edpm,openstackdataplaneservice=bootstrap
  configure-network-edpm-scale-in-2-openstack-edpm   Complete  1/1  app=openstackansibleee,openstackdataplanedeployment=edpm-scale-in-2,openstackdataplanenodeset=openstack-edpm,openstackdataplaneservice=configure-network
  ```

- The commands that work are the ones of the lab's own
  [data plane troubleshooting page](../../docs/troubleshooting/dataplane.md).

**Not verified on the lab:**

- The exact error text of `oc get openstackansibleee` was not captured;
  capture it for the pull request.
- The lab runs 18-stable; the Job naming and labels on `main` were read
  in the code, not observed.

## Upstream state

Looked at on 2026-11-13, `main` at `1a58205d24a6e9aeac5a2de15a302ea597b2c9eb`.

| Fact | Pointer |
| --- | --- |
| Page uses `oc get openstackansibleee` four times, and `oc logs job/<service>` with a Job named `repo-setup-openstack-edpm` | [`docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc`](https://github.com/openstack-k8s-operators/openstack-operator/blob/1a58205d24a6e9aeac5a2de15a302ea597b2c9eb/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc), L28, L34, L46, L54, L71 |
| Last change of the page | commit `52401d5b55` "Add dataplane docs", 2024-06-17 (GitHub commit list for the path) |
| The custom resource was replaced by Jobs | pull request #972 "Use ansibleEE library instead of AnsibleEE v1 CR", closed 2024-07-25 |
| Labels set on the Jobs today | `internal/dataplane/util/ansible_execution.go` L252-L254 (`openstackdataplaneservice`, `openstackdataplanedeployment`, `openstackdataplanenodeset`) |
| A sibling page already uses a selector that works | `docs/assemblies/logs.adoc` L34 (`oc get pods -l app=openstackansibleee`) |
| Documentation is maintained in this directory | six commits under `docs/assemblies` between 2026-09-30 and 2026-10-15; approvers alias `docs-approvers` in `docs/OWNERS` |

Duplicate search on 2026-11-13 (issues and pull requests, open and
closed, in `openstack-k8s-operators/openstack-operator`):
"oc get openstackansibleee" (#972 and #1018, neither touches the page),
"troubleshooting data plane docs ansibleee" (0), "docs
openstackansibleee" (#1080, unrelated). No open pull request changes the
page.

**Not specific to the lab.** The published product documentation is
maintained elsewhere and was not compared; this topic is only about the
upstream page.

## Proposed contribution

One pull request against `main` that rewrites the commands of the page:

- `oc get job -l openstackdataplanedeployment=<deployment>` in place of
  the removed resource, with a real sample output;
- how to read the conditions that replaced the "job condition message"
  column (`oc get openstackdataplanedeployment <name> -o yaml`, the
  per-NodeSet conditions);
- `oc logs job/<service>-<deployment>-<nodeset>` or
  `oc logs -l openstackdataplaneservice=<service>,openstackdataplanedeployment=<deployment>`;
- keep the structure and tone of the page; do not add new sections in the
  same pull request.

## Reproduction and validation plan

1. `[READ-ONLY]` Capture on the lab: the error of
   `oc get openstackansibleee`, the Job list with labels for one
   deployment, the conditions of a finished and of a failed deployment
   (one exists in the lab history), `oc logs` with the selector.
2. Replace host names and addresses in the samples with the generic ones
   the upstream pages already use (`openstack-edpm`, `edpm-compute-0`).
3. Build the documentation locally with `make docs` (Makefile target
   `docs`) and read the rendered page.
4. Check the Job naming on `main` in the code before writing the sample.

## Effort and risk

- Half a day including captures and the local build.
- Risk: the maintainers may prefer to drop the page or to merge it with
  `logs.adoc`. Ask in the pull request description, accept either.

## Review-readiness checklist

- [ ] Error of the old command captured
- [ ] New commands run on the lab, outputs captured and made generic
- [ ] Job naming confirmed on `main`
- [ ] `make docs` builds, page read in the browser
- [ ] Commit with `Signed-off-by`; description says what was tested and
      on which version

## Open questions

- Is there a Jira component for documentation, or is a pull request
  without a ticket fine for docs? Look at recent docs-only pull requests
  before sending.
- Does `logs.adoc` need the same refresh (its sample pod names predate
  the current Job naming)? If yes, a second small pull request.

## Draft pull request text

> **Title:** docs: update data plane troubleshooting commands after the
> removal of the OpenStackAnsibleEE resource
>
> The troubleshooting page still lists services with
> `oc get openstackansibleee`. That resource was replaced by Jobs in
> #972, so the command now fails, and the Job name used in the `oc logs`
> example no longer matches the current naming.
>
> This change replaces the commands with label selectors on the Jobs
> (`openstackdataplanedeployment`, `openstackdataplaneservice`) and shows
> where the conditions are reported now. Sample outputs were captured on
> an 18-stable deployment and made generic.
>
> Tested: commands run on OKD 4.22 with the 18-stable operators;
> documentation built with `make docs`.
