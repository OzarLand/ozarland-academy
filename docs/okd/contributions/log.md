---
title: "Contribution journal"
description: "One entry per action taken towards upstream, newest first. The journal is the memory of the contribution effort: what was sent, where, and what came back."
---

# Contribution journal

One entry per action taken towards upstream, newest first. The journal is
the memory of the contribution effort: what was sent, where, and what came
back. Nothing has been sent upstream yet: the entries so far are lab
observations and code reading.

## Entry format

```markdown
## YYYY-MM-DD — short title

- **Topic:** [NN-slug](topics/NN-slug.md)
- **Action:** what was done (lab validation run, issue filed, patch sent,
  review answered, question asked on a channel)
- **Link:** URL of the issue, pull request, review or thread; path of the
  evidence when the action was a lab run
- **Outcome:** what came back (confirmed, needs information, rejected with
  the reason, merged with the commit, no answer yet)
- **Next step:** the next action and who is expected to take it
```

Rules:

- Write the entry the same day as the action, including for actions that
  led nowhere: a rejected report is information for the next one.
- A lab run is an action. Record what was run, on which versions, and what
  was observed, before any claim is made upstream.
- When an entry changes the state of a topic, update the status board in
  [README.md](index.md) in the same commit.
- No addresses, host names or credentials of the host environment, here as
  everywhere else in the repository.

## Entries

## 2026-11-14 — Refusal and confirmed deletion of a running deployment captured

- **Topic:** [08-dataplane-confirm-delete-annotation-undocumented](topics/08-dataplane-confirm-delete-annotation-undocumented.md)
- **Action:** lab run on `openstack-operator.v0.8.0`: a test deployment
  limited to a service that runs `sleep 150` on the compute node was
  deleted while in progress, first without and then with the annotation
  `dataplane.openstack.org/confirm-delete=true`; a second test
  deployment in error was deleted without the annotation. Upstream
  `main` re-read at `85bcf36`, duplicate search repeated.
- **Link:** evidence in the topic file (section "Refusal and confirmed
  deletion on a test deployment")
- **Outcome:** confirmed. Deletion refused with the warning and the
  "Forbidden" message; accepted once annotated; Job, pod and the task on
  the node gone within 5 seconds; no annotation needed for a failed
  deployment; NodeSet back to "NodeSet Ready". Proposed block for the
  troubleshooting page written as a diff against `main`.
- **Next step:** owner: build the page with `make docs`, then open the
  documentation pull request (after topic 07 or together with it).

## 2026-11-14 — Backup and restore scripts: three effects replayed, patched copies run

- **Topic:** [02-galera-backup-restore-scripts-lose-errexit](topics/02-galera-backup-restore-scripts-lose-errexit.md)
- **Action:** lab run, 10:23 to 10:26 UTC, operators of
  `openstack-operator.v0.8.0` (18-stable), instance `openstack-cell1`,
  after a logical dump of both instances had been set aside. Backup
  Jobs built from the CronJob: unmodified script with `mysqldump`
  replaced by a failing test double; patched script with the same
  double; patched script with the real `mysqldump`. Restore script in
  the pod of a `GaleraRestore`: invalid file and `SIGTERM` during a
  load, each with the unmodified and the patched script. `main`
  re-read, duplicate search redone; `bashate` and `go test ./...` run in
  a scratch clone of `main` with the diff applied.
- **Link:** lab evidence directory `contrib/02/`, files 01 to 06
- **Outcome:** unmodified: failed dump published as an 87-byte file by a
  successful Job; failed restore exits 0; interrupted restore leaves
  the Service without endpoint (the API refuses the selector value with
  braces). Patched: Job fails and publishes nothing, restore exits 1,
  the endpoint is put back, a normal backup still completes. Service
  repaired by hand after the unmodified interrupted run (22 s without
  endpoint). Not run: chainsaw suites, an operator built from `main`, a
  three-member instance. Test objects and files removed.
- **Next step:** the sender writes the negative chainsaw test, runs the
  chainsaw suites on a scratch cluster, then opens the pull request
  (diff and text in the topic).

## 2026-11-14 — GaleraBackup retention: reproduced with markers, proposed line run

- **Topic:** [01-galerabackup-retention-deletes-nothing](topics/01-galerabackup-retention-deletes-nothing.md)
- **Action:** lab run, 10:22 to 10:24 UTC, same versions and instance.
  Three marker files dated 2026-08-01 placed on the backup volume;
  `retention: 10m` set on the `GaleraBackup` (CronJob `RETENTION=10`),
  one Job created from the CronJob; then `retention` put back to 72 h
  and one Job with a copy of the script carrying the proposed `find`
  line. `main` re-read, duplicate search redone.
- **Link:** lab evidence directory `contrib/01/`, files 00 to 02
- **Outcome:** unmodified script: nothing deleted, only the marker named
  `<instance>….sql` printed. Proposed line: the two aged
  `openstack_backup*.sql.gz` markers deleted, files younger than 72 h
  kept, new dump valid. Markers and test dumps removed, `retention`
  back to `72h0m0s`.
- **Next step:** the sender writes the chainsaw step, runs the chainsaw
  suites on a scratch cluster, then opens the pull request (diff and
  text in the topic).

## 2026-11-14 — Bootstrap packages: image file compared, masked failure replayed

- **Topic:** [04-edpm-bootstrap-masked-package-failure-backport](topics/04-edpm-bootstrap-masked-package-failure-backport.md)
- **Action:** lab run, 10:14 to 10:17 UTC, runner image of
  `openstack-operator.v0.8.0` (18-stable), CentOS Stream 9 node:
  `packages.yml` read from the image and compared by checksum with
  `18-stable` at `2317faf8`; three throw-away services run through
  short deployments (real task file with a missing package; tasks of
  `main` at `3e5e2930` inline with the missing package, then with the
  17 default packages); `rpm -V` with and without `--noconfig` on the
  node. Upstream branches re-read, duplicate search redone.
- **Link:** lab evidence directory `contrib/04/`, files 01 to 04
- **Outcome:** file identical to the branch; on CentOS both tasks are
  green with `dnf` rc 1 and `rpm -V` rc 1; the tasks of `main` fail on
  the `dnf` task and pass with the real list; `--noconfig` is needed on
  a deployed node. Not run: molecule, a runner image built from the
  backport. Test resources deleted, NodeSet Ready.
- **Next step:** the sender files the issue (draft in the topic) after
  checking the tracker ticket if an account is available.

## 2026-11-14 — Troubleshooting page: old and new commands captured

- **Topic:** [07-dataplane-troubleshooting-doc-removed-resource](topics/07-dataplane-troubleshooting-doc-removed-resource.md)
- **Action:** lab run on `openstack-operator.v0.8.0` (18-stable), OKD
  4.22.0-okd-scos.10, 10:02 to 10:08 UTC: the two commands of the
  upstream page, then a test deployment of two throw-away services (one
  waits 150 s, one fails, `backoffLimit: 1`) observed while running and
  after its failure with Job selectors, `oc logs` and the conditions.
  Upstream `main` re-read at `85bcf368e8`; duplicate search redone.
- **Link:** lab evidence directory `contrib/07/`, files 01 to 04
- **Outcome:** error texts captured; replacement commands and messages
  confirmed on the lab; replacement text written as a diff against
  `main`. Not done: `make docs` (no Ruby toolchain on the workstation).
  Test deployment and services deleted, NodeSet back to Ready.
- **Next step:** the sender builds the documentation, signs off the
  commit and opens the pull request; ask in it whether a tracker ticket
  is required.

## 2026-11-14 — OVN agents: recovery without restart timed, code read

- **Topic:** [05-ovn-agents-stuck-after-dns-outage](topics/05-ovn-agents-stuck-after-dns-outage.md)
- **Action:** read-only observation of a start of the whole lab that
  nobody provoked (package `ovn24.03-24.03.8-55.el9s`, Open vSwitch
  library 3.3.8, `unbound-libs` 1.26.1, one nameserver); journals of
  the two previous boots re-read; Open vSwitch, OVN, Unbound and
  edpm-ansible sources read. No outage was provoked and nothing was
  changed on the node.
- **Link:** lab evidence directory `ovn-stuck/`, files 01 to 11
- **Outcome:** the agents reconnect by themselves, 15 and 16 minutes
  after their start; "never reconnect" and "18 hours" withdrawn; the
  shipped Unbound file is in the lab build and does not prevent the
  delay; origin of the error text established in the code; mechanism
  of the delay (libunbound infrastructure cache, 900 s) probable, not
  proven. Topic 06 corrected on the same points.
- **Next step:** a provoked DNS outage with a packet capture, then
  the same with `infra-keep-probing: yes` (plan in the topic); to be
  decided by the lab owner. Nothing to send upstream before that.

## 2026-11-14 — OVN agents: DNS outage provoked with a capture, file as deployed

- **Topic:** [05-ovn-agents-stuck-after-dns-outage](topics/05-ovn-agents-stuck-after-dns-outage.md)
- **Action:** capture of port 53 on the compute node; DNS service of
  the control plane scaled to zero from 10:38:09 to about 10:44 UTC;
  connections of the node to the southbound database closed at
  10:38:23; agents left alone (running since 07:38).
- **Link:** lab evidence directory `contrib/05/`, files `run1-baseline.*`
- **Outcome:** node resolves again at 10:44:25; no query for the
  database name in the capture until 10:53:27, while 90 errors are
  logged; both agents connected at 10:53:27-28, 904 s after the drop.
  Cause established.
- **Next step:** same outage with each candidate setting.

## 2026-11-14 — OVN agents: same outage with `infra-keep-probing: yes`

- **Topic:** [05-ovn-agents-stuck-after-dns-outage](topics/05-ovn-agents-stuck-after-dns-outage.md)
- **Action:** setting added to the two Unbound files on the node,
  both services restarted at 10:59:40; DNS service away from 11:00:35
  to about 11:06:50; connections closed at 11:00:50.
- **Link:** lab evidence directory `contrib/05/`, files `run2-keep-probing.*`
- **Outcome:** node resolves again at 11:06:58; all three processes
  connected by 11:07:48 (50 s). Side effect: the controller logged
  poll intervals of about 120 s during the whole outage.
- **Next step:** same outage with a short `infra-host-ttl`.

## 2026-11-14 — OVN agents: same outage with `infra-host-ttl: 60`

- **Topic:** [05-ovn-agents-stuck-after-dns-outage](topics/05-ovn-agents-stuck-after-dns-outage.md)
- **Action:** `infra-host-ttl: 60` instead of the previous setting,
  both services restarted at 11:08:58; DNS service away from 11:09:53
  to about 11:16:10; connections closed at 11:10:08. Then both files
  put back as deployed and both services restarted at 11:17:16.
  Installed `unbound-libs` 1.26.1 compared with the sources at its
  tag; upstream state and duplicate search redone.
- **Link:** lab evidence directory `contrib/05/`, files `run3-host-ttl-60.*`
- **Outcome:** node resolves again at 11:16:12; all three processes
  connected at 11:16:23 (11 s). One poll interval of 312 s on the
  controller. Node back to the deployed files, agents connected,
  containers healthy.
- **Next step:** the sender reads the tracker ticket OSPRH-38451,
  adapts the draft to the issue template and opens the issue; a pull
  request on the two default files only if a maintainer asks.
