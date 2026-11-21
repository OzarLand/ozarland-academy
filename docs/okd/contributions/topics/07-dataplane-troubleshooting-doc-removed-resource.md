# 07 — The data plane troubleshooting page still uses a resource that was removed in 2024

- **Target:** `openstack-k8s-operators/openstack-operator`, branch `main`
  (documentation under `docs/assemblies/`)
- **Type:** documentation fix
- **Effort:** small (one AsciiDoc page, commands and sample outputs to
  replace with ones captured on the lab)
- **Status:** candidate, lab evidence complete — the error of the old
  command and every replacement command were captured on the lab on
  2026-11-14, and the replacement text is ready as a diff. Left for the
  sender: the documentation build and the sign-off
- **Upstream state checked on:** 2026-11-14

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

Lab: `openstack-operator.v0.8.0` (18-stable catalog), OKD
4.22.0-okd-scos.10, one NodeSet `openstack-edpm` with one node. All
captures below were run on 2026-11-14 between 10:02 and 10:08 UTC
(lab evidence directory `contrib/07/`, files 01 to 03).

The old commands of the page:

```console
$ oc get openstackansibleee
error: the server doesn't have a resource type "openstackansibleee"
$ oc logs job/repo-setup-openstack-edpm
error: error from server (NotFound): jobs.batch "repo-setup-openstack-edpm" not found in namespace "openstack"
```

`oc api-resources` lists three `dataplane.openstack.org` kinds
(deployments, node sets, services) and `ansibletests`; nothing else
matches "ansible".

The replacement, during a test deployment of two throw-away services
(one that waits, one that fails on purpose, `backoffLimit: 1`):

```console
$ oc get job -l openstackdataplanedeployment=test-deployment
NAME                                         STATUS    COMPLETIONS   DURATION   AGE
test-wait-test-deployment-openstack-edpm     Running   0/1           50s        50s
$ oc get openstackdataplanedeployment test-deployment -o jsonpath='{range .status.nodeSetConditions.openstack-edpm[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\t"}{.message}{"\n"}{end}'
NodeSetDeploymentReady         False  Requested  Deployment not yet ready for test-wait service
ServiceTestWaitDeploymentReady False  Requested  Deployment not yet ready for test-wait service
$ oc logs job/test-wait-test-deployment-openstack-edpm --tail=1
TASK [Harmless long task on the node] ******************************************
```

After the second service failed twice (10:06:58):

```console
$ oc get job -l openstackdataplanedeployment=test-deployment
NAME                                         STATUS     COMPLETIONS   DURATION   AGE
test-fail-test-deployment-openstack-edpm     Failed     0/1           37s        37s
test-wait-test-deployment-openstack-edpm     Complete   1/1           3m4s       3m41s
$ oc get pods -l openstackdataplanedeployment=test-deployment
NAME                                               READY   STATUS      RESTARTS   AGE
test-fail-test-deployment-openstack-edpm-22gjl     0/1     Error       0          37s
test-fail-test-deployment-openstack-edpm-hjlv6     0/1     Error       0          25s
test-wait-test-deployment-openstack-edpm-lgfjc     0/1     Completed   0          3m41s
$ oc get openstackdataplanedeployment test-deployment -o jsonpath='{range .status.nodeSetConditions.openstack-edpm[*]}{.type}{"\t"}{.status}{"\t"}{.reason}{"\t"}{.message}{"\n"}{end}'
NodeSetDeploymentReady         False  BackoffLimitExceeded  Deployment error occurred in test-fail service error backoff limit reached for execution.name test-fail-test-deployment-openstack-edpm execution.namespace openstack execution.condition.message: Job has reached the specified backoff limit
ServiceTestFailDeploymentReady False  BackoffLimitExceeded  Deployment error occurred in test-fail service error backoff limit reached for execution.name test-fail-test-deployment-openstack-edpm execution.namespace openstack execution.condition.message: Job has reached the specified backoff limit
ServiceTestWaitDeploymentReady True   Ready                 Deployment ready for test-wait service
$ oc logs -l openstackdataplanedeployment=test-deployment,openstackdataplaneservice=test-fail --tail=3 --prefix
[pod/test-fail-test-deployment-openstack-edpm-22gjl/...] PLAY RECAP *********************************************************************
[pod/test-fail-test-deployment-openstack-edpm-22gjl/...] edpm-compute-0             : ok=0    changed=0    unreachable=0    failed=1    skipped=0    rescued=0    ignored=0
[pod/test-fail-test-deployment-openstack-edpm-22gjl/...] EDPM AEE SUMMARY: status=failed rc=2 total_hosts=1 failed_hosts=1 unreachable_hosts=0 last_task=- last_host=-
```

Names are made generic in these samples (`test-deployment`,
`test-wait`, `test-fail`); columns are realigned and the `--prefix`
field is shortened. Other facts observed in the same run:

- The same failure text is the `MESSAGE` of
  `oc get openstackdataplanedeployment` and of
  `oc get openstackdataplanenodeset` (`Deployment error occurred
  nodeSet: openstack-edpm error: backoff limit reached ...` on the
  deployment).
- The Job carries the conditions `FailureTarget` and `Failed`, reason
  `BackoffLimitExceeded`.
- Every Job of the data plane has the label `app=openstackansibleee`
  and the three labels `openstackdataplanedeployment`,
  `openstackdataplanenodeset`, `openstackdataplaneservice`. The Job of
  a service that runs once for all NodeSets (`ssh-known-hosts`) is
  named `<service>-<deployment>`, without the NodeSet name and without
  the NodeSet label.
- For a deployment finished 28 hours earlier, `oc logs job/...`
  answered `unable to retrieve container logs for cri-o://...`: the
  pod is still listed but its log is gone. The page should not promise
  logs of old runs.
- The failed test deployment was deleted afterwards; the NodeSet
  returned to `True`, "NodeSet Ready" within 15 seconds. The two test
  services were removed.

**Not verified on the lab:**

- The lab runs 18-stable; the Job naming, labels and condition messages
  on `main` were read in the code (pointers below), not observed.
- The documentation build (`make docs`) was not run: the Ruby toolchain
  it needs is not available on the workstation used. The proposed text
  was not rendered.
- The published product documentation was not compared.

## Upstream state

Looked at on 2026-11-14, `main` at `85bcf368e833d5d8c4246d3e5a8e9d3c911d008e`
(commit of 2026-11-13). The page is identical to the one read on
2026-11-13.

| Fact | Pointer |
| --- | --- |
| Page uses `oc get openstackansibleee` four times, and `oc logs job/<service>` with a Job named `repo-setup-openstack-edpm` | [`docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc`](https://github.com/openstack-k8s-operators/openstack-operator/blob/85bcf368e833d5d8c4246d3e5a8e9d3c911d008e/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc), L28, L34, L46, L54, L71 |
| Last change of the page | commit `52401d5b55` "Add dataplane docs", 2024-06-17 (GitHub commit list for the path) |
| The custom resource was replaced by Jobs | pull request #972 "Use ansibleEE library instead of AnsibleEE v1 CR", closed 2024-07-25 |
| Job name `<service>-<deployment>`, plus `-<nodeset>` unless the service is deployed on all NodeSets; shortened with a hash above 63 characters | `internal/dataplane/util/ansible_execution.go` L258-L279 |
| Labels set on the Jobs | same file L252-L254 (`openstackdataplaneservice`, `openstackdataplanedeployment`, `openstackdataplanenodeset`); `internal/dataplane/util/ansibleee.go` L206 (`app: openstackansibleee`) |
| Condition messages per service | `api/dataplane/v1beta1/conditions.go` L99-L105 ("Deployment ready for %s service", "Deployment not yet ready for %s service", "Deployment error occurred in %s service") |
| Failure detail appended to the message | `internal/dataplane/deployment.go` L324 ("backoff limit reached for execution.name %s execution.namespace %s execution.condition.message: %s") |
| Sibling pages already use a selector that works | `docs/assemblies/logs.adoc` L34, `docs/assemblies/proc_deploying-the-data-plane.adoc` L58-L59 (`-l app=openstackansibleee`) |
| Documentation is maintained in this directory | approvers alias `docs-approvers` in `docs/OWNERS` |

Duplicate search on 2026-11-14 with the GitHub search API
(`repo:openstack-k8s-operators/openstack-operator <words>`, issues and
pull requests, open and closed):

| Query words | Result |
| --- | --- |
| `"oc get openstackansibleee"` | 0 |
| `troubleshooting data plane docs ansibleee` | 0 |
| `docs openstackansibleee` | 1: #1080 (closed pull request of 2024-09-17, unrelated) |
| `troubleshooting-data-plane-creation` | 0 |

No issue or pull request, open or closed, is about this page.

**Not specific to the lab.** The published product documentation is
maintained elsewhere and was not compared; this topic is only about the
upstream page.

## Proposed contribution

One pull request against `main` that rewrites the first part of the
page and leaves its last section ("Check service pod status reports")
untouched. The diff below is against the file at
`85bcf368e833d5d8c4246d3e5a8e9d3c911d008e`; it keeps the structure, the
tone and the example names of the page (`openstack-edpm-ipam1`). The
sample outputs follow the format captured on the lab; the example
names and durations are illustrative, as in the current page.

```diff
--- a/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc
+++ b/docs/assemblies/proc_troubleshooting-data-plane-creation-and-deployment.adoc
@@ -2,7 +2,7 @@
 = Troubleshooting data plane creation and deployment
 
 [role="_abstract"]
-Each data plane deployment in the environment has associated services. Each of these services have a job condition message that matches to the current status of the AnsibleEE job executing for that service. This information can be used to troubleshoot deployments when services are not deploying or operating correctly.
+Each data plane deployment in the environment has associated services. Each of these services is executed by a Kubernetes Job that runs Ansible, and the deployment reports a condition for each service. This information can be used to troubleshoot deployments when services are not deploying or operating correctly.
 
 .Procedure
 
@@ -22,53 +22,68 @@
 openstack-edpm-ipam2   ["openstack-edpm"]   False    Deployment in progress
 ----
 
-. Determine the name and status of all services and their job condition:
+. Determine the name and status of the jobs of all services:
 +
 ----
-$ oc get openstackansibleee
+$ oc get job -l app=openstackansibleee
 ----
 +
-The following example output shows all services and their job condition for all current deployments:
+The following example output shows the jobs of all services for all current deployments. The name of a job is `<service>-<deployment_name>-<nodeset_name>`, or `<service>-<deployment_name>` for a service that runs once for all node sets:
 +
 ----
-$ oc get openstackansibleee
+$ oc get job -l app=openstackansibleee
 
-NAME                             NETWORKATTACHMENTS   STATUS   MESSAGE
-bootstrap-openstack-edpm         ["ctlplane"]         True     Job completed
-download-cache-openstack-edpm    ["ctlplane"]         False    Job in progress
-repo-setup-openstack-edpm        ["ctlplane"]         True     Job completed
-validate-network-another-osdpd   ["ctlplane"]         False    Job in progress
+NAME                                                   STATUS     COMPLETIONS   DURATION   AGE
+bootstrap-openstack-edpm-ipam1-openstack-edpm          Complete   1/1           2m34s      5m
+download-cache-openstack-edpm-ipam1-openstack-edpm     Running    0/1           50s        50s
+repo-setup-openstack-edpm-ipam1-openstack-edpm         Complete   1/1           20s        5m20s
+validate-network-openstack-edpm-ipam2-openstack-edpm   Running    0/1           8s         8s
 ----
 
-. Filter for the name and service for a specific deployment:
+. Filter the jobs for a specific deployment:
 +
 ----
-$ oc get openstackansibleee -l openstackdataplanedeployment=<deployment_name>
+$ oc get job -l openstackdataplanedeployment=<deployment_name>
 ----
 +
-* Replace `<deployment_name>` with the name of the deployment to use to filter the services list.
+* Replace `<deployment_name>` with the name of the deployment to use to filter the jobs list.
 +
-The following example filters the list to only show services and their job condition for the `openstack-edpm-ipam1` deployment:
+The following example filters the list to only show the jobs of the `openstack-edpm-ipam1` deployment:
 +
 ----
-$ oc get openstackansibleee -l openstackdataplanedeployment=openstack-edpm-ipam1
+$ oc get job -l openstackdataplanedeployment=openstack-edpm-ipam1
 
-NAME                            NETWORKATTACHMENTS   STATUS   MESSAGE
-bootstrap-openstack-edpm        ["ctlplane"]         True     Job completed
-download-cache-openstack-edpm   ["ctlplane"]         False    Job in progress
-repo-setup-openstack-edpm       ["ctlplane"]         True     Job completed
+NAME                                                 STATUS     COMPLETIONS   DURATION   AGE
+bootstrap-openstack-edpm-ipam1-openstack-edpm        Complete   1/1           2m34s      5m
+download-cache-openstack-edpm-ipam1-openstack-edpm   Running    0/1           50s        50s
+repo-setup-openstack-edpm-ipam1-openstack-edpm       Complete   1/1           20s        5m20s
 ----
 
-.Job Condition Messages
+. Display the condition of each service of a deployment:
++
+----
+$ oc get openstackdataplanedeployment <deployment_name> -o jsonpath='{range .status.nodeSetConditions.<nodeset_name>[*]}{.type}{"\t"}{.status}{"\t"}{.message}{"\n"}{end}'
+----
++
+* Replace `<nodeset_name>` with the name of a node set of the deployment.
++
+The following example shows a deployment where the `bootstrap` service is complete and the `download-cache` service is in progress:
++
+----
+NodeSetDeploymentReady                False   Deployment not yet ready for download-cache service
+ServiceBootstrapDeploymentReady       True    Deployment ready for bootstrap service
+ServiceDownloadCacheDeploymentReady   False   Deployment not yet ready for download-cache service
+----
+
+.Service Condition Messages
 
-AnsibleEE jobs have an associated condition message that indicates the current state of the service job. This condition message is displayed in the `MESSAGE` field of the `oc get openstackansibleee` command output. Jobs return one of the following conditions when queried:
+Each service has an associated condition message that indicates the current state of the job executing that service. This condition message is displayed in the `status.nodeSetConditions` field of the `OpenStackDataPlaneDeployment` resource. Services return one of the following conditions when queried:
 
-* `Job not started`: The job has not started.
-* `Job in progress`: The job is currently running.
-* `Job completed`: The job execution is complete.
-* `Job error occured <error_message>`: The job execution stopped unexpectedly. The `<error_message>` is replaced with a specific error message.
+* `Deployment not yet ready for <service> service`: The job has not completed.
+* `Deployment ready for <service> service`: The job execution is complete.
+* `Deployment error occurred in <service> service error backoff limit reached for execution.name <job_name> execution.namespace <namespace> execution.condition.message: <error_message>`: The job execution failed and was retried until the backoff limit of the deployment was reached. The same message is displayed in the `MESSAGE` field of the `oc get openstackdataplanedeployment` and `oc get openstackdataplanenodeset` command output.
 
-To further investigate a service displaying a particular job condition message, use the command `oc logs job/<service>` to display the logs associated with that service. For example, to display the logs for the `repo-setup-openstack-edpm` service, use the command `oc logs job/repo-setup-openstack-edpm`.
+To further investigate a service displaying a particular condition message, use the command `oc logs job/<service>-<deployment_name>-<nodeset_name>` to display the logs associated with that service. For example, to display the logs for the `repo-setup` service of the `openstack-edpm-ipam1` deployment on the `openstack-edpm` node set, use the command `oc logs job/repo-setup-openstack-edpm-ipam1-openstack-edpm`. To display the logs of every attempt of a failed service, select the pods with labels: `oc logs -l openstackdataplanedeployment=<deployment_name>,openstackdataplaneservice=<service> --prefix`.
 
 
 .Check service pod status reports
```

To apply: save the block as a file and run `git apply` in a clone at
that commit, or redo the edit by hand if the page has moved.

## Reproduction and validation plan

1. Done on 2026-11-14: error of the old commands, Job list with labels,
   conditions of a running, a finished and a failed deployment,
   `oc logs` by Job name and by selector.
2. Done: names made generic in the samples.
3. To do by the sender: build the documentation with `make docs`
   (needs `bundle`; Makefile target `docs`) and read the rendered page,
   in particular the long `jsonpath` line.
4. Done by reading: Job naming and messages on `main` (pointers above).

## Effort and risk

- Half a day including captures and the local build.
- Risk: the maintainers may prefer to drop the page or to merge it with
  `logs.adoc`. Ask in the pull request description, accept either.

## Review-readiness checklist

- [x] Error of the old command captured (2026-11-14)
- [x] New commands run on the lab, outputs captured and made generic
      (2026-11-14, 18-stable)
- [x] Job naming confirmed on `main` by reading the code (not run)
- [ ] `make docs` builds, page read in the browser
- [ ] Commit with `Signed-off-by`; description says what was tested and
      on which version

## Open questions

- Is a pull request without a ticket fine for docs? Two merged
  documentation pull requests sampled on 2026-11-14 (#1699 of
  2025-11-18, #1974 of 2026-07-07) both reference a tracker ticket in
  their description and carry `Signed-off-by`. The tracker needs an
  account and was not read. A sender without a ticket should say so in
  the description and ask whether one is needed.
- Does `logs.adoc` need the same refresh (its sample pod names predate
  the current Job naming)? If yes, a second small pull request.

## Draft pull request text

> **Title:** docs: update data plane troubleshooting commands after the
> removal of the OpenStackAnsibleEE resource
>
> The troubleshooting page still lists services with
> `oc get openstackansibleee`. That resource was replaced by Jobs in
> #972, so the command now answers `error: the server doesn't have a
> resource type "openstackansibleee"`, and the Job name used in the
> `oc logs` example no longer exists (Jobs are named
> `<service>-<deployment>-<nodeset>`).
>
> This change replaces the commands with label selectors on the Jobs
> (`app=openstackansibleee`, `openstackdataplanedeployment`,
> `openstackdataplaneservice`), shows where the per-service conditions
> are reported now (`status.nodeSetConditions` of the deployment) and
> lists the current condition messages. The last section of the page is
> unchanged.
>
> Tested: the commands were run on OKD 4.22 with the 18-stable
> operators (`openstack-operator.v0.8.0`) against a running, a finished
> and a failed deployment; names in the samples are generic. Job naming
> and messages on `main` were checked in the code
> (`internal/dataplane/util/ansible_execution.go`,
> `api/dataplane/v1beta1/conditions.go`). Documentation built with
> `make docs`. <!-- keep this sentence only once the build was run -->
