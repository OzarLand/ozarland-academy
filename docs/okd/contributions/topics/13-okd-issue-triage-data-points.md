---
title: "13 — OKD 4.22 open issues: data points from a healthy single-node cluster"
description: "The OKD tracker has reports against the exact build the lab runs (4.22.0-okd-scos.10) and its predecessors."
seo_title: "13 — OKD 4.22 open issues: data points"
---

# 13 — OKD 4.22 open issues: data points from a healthy single-node cluster

- **Target:** `okd-project/okd` (GitHub issues), branch not applicable
- **Type:** triage help (comments with evidence on existing reports), no
  code
- **Effort:** small per issue
- **Status:** candidate, modest value — the lab does **not** reproduce
  any of the three reports; it can only say "not seen here, with this
  configuration", which is useful to narrow a cause but is not a fix
- **Upstream state checked on:** 2026-11-13

## Summary

The OKD tracker has reports against the exact build the lab runs
(`4.22.0-okd-scos.10`) and its predecessors. A maintainer team that
small needs people who run the same build and answer "do you see it
too?" with facts. Three reports were compared with the lab. In each case
the lab is a counter-example, and the difference in configuration is the
interesting part.

This is the slowest way to be noticed and the cheapest way to be useful.
It suits the periods when no code topic is in progress.

## Why it matters in production

- The reports concern etcd, time synchronisation and API server
  monitoring: the layer every OpenStack control plane on OKD depends on.
- Knowing which of these the lab build is exposed to is needed anyway
  before trusting the platform; writing it down upstream costs little
  more.

## Evidence from the lab

Lab: OKD `4.22.0-okd-scos.10`, single node, agent-based installation,
internal NTP source. All reads below are read-only.

| Upstream report | What the lab shows | Date read |
| --- | --- | --- |
| #2357 etcd operator loops on "currentRevision: cannot be unset once set" when etcd cannot start | Not affected: `Etcd/cluster` has one node status with `currentRevision: 3`, the etcd operator is Available and not degraded | 2026-11-13 |
| #2341 `chrony-wait.service` fails at boot (reported on `.5`) | Not seen: no failed systemd unit on the node | 2026-11-12 |
| #2330 "apiserver target down" alerts since 4.22 | Not seen: six alerts firing on the lab, none is `TargetDown` | 2026-11-12 |

**Not verified on the lab:**

- No attempt was made to provoke #2357 (it needs etcd to be unable to
  start at installation time; the report describes three control plane
  nodes with a blocked network path).
- The chrony configuration of the lab was not compared line by line with
  the reporter's.
- The scrape targets of #2330 were not listed on the lab; only the
  alerts were.

## Upstream state

Looked at on 2026-11-13.

| Report | State | Pointer |
| --- | --- | --- |
| #2357 "cluster-etcd-operator deadlocks on currentRevision ..." | open since 2026-09-16, no label, no assignee; two comments, both by the reporter on 2026-11-10 asking for triage and adding a link to evidence | `okd-project/okd` issue #2357 |
| #2341 "chrony-wait.service fails during node boot" | open since 2026-07-07, `kind/bug`, two assignees; one maintainer comment on 2026-08-25 ("we have seen this previously") | issue #2341 |
| #2330 "Apiserver target reported down" | open since 2026-05-18, `kind/bug`, assigned, nine comments, last update 2026-09-01 | issue #2330 |

How the tracker works, from the repository itself (`master` at
`389a9fb6dcf1`): blank issues are disabled; the bug form asks for
version, reproducibility and a log bundle; troubleshooting questions are
directed to the organisation's discussions
(`.github/ISSUE_TEMPLATE/config.yml`).

The analysis in #2357 points at a validation rule of the `Etcd` resource
defined in `openshift/api`. That part was **not** verified here: the
rule and the operator code were not read.

**Lab-specific by nature:** a counter-example only has value with its
configuration attached.

## Proposed contribution

In order of usefulness:

1. \#2357: read the validation rule and the operator code path the
   reporter names, and confirm or correct the analysis in a comment. An
   untriaged report with a precise analysis is where a second reader
   helps most. A single-node data point ("revision 3, no loop") can be
   added, clearly marked as a different topology.
2. \#2341: post the chrony unit state and the time-source configuration
   of a node where the unit does not fail, so the difference can be
   found.
3. #2330: only if the scrape targets of the lab are compared first;
   otherwise there is nothing to add.

One comment per issue, facts only, no "+1".

## Reproduction and validation plan

1. `[READ-ONLY]` #2357:
   `oc get etcd cluster -o jsonpath='{.status.nodeStatuses}'`,
   `oc get co etcd`; read the rule in `openshift/api` at the commit the
   4.22 payload uses.
2. `[READ-ONLY]` #2341: on the node, `systemctl status chrony-wait`,
   `chronyc sources`, `systemctl --failed`; the machine configuration
   that sets the time source.
3. `[READ-ONLY]` #2330: list the targets of the service monitor named in
   the report in the monitoring console.
4. `[DESTRUCTIVE]` Reproducing #2357 needs a throw-away multi-node
   installation with a blocked etcd peer path. Not planned; mention
   honestly that it was not done.

## Effort and risk

- One to three hours per issue.
- Risk: a comment that adds no information is noise. Do not post unless
  the comment contains something a maintainer could not get from the
  report.
- Visibility is low and slow; this is groundwork, not a headline.

## Review-readiness checklist

- [ ] Report re-read on the day, including new comments
- [ ] Lab facts captured the same day, with versions
- [ ] Topology difference stated in the first sentence
- [ ] Any code analysis carries file, line and commit
- [ ] Output cleaned of addresses and names of the hosting environment

## Open questions

- Does the working group prefer such data points on the issue or in the
  discussions? Read a few recently closed issues to see what maintainers
  reacted to.
- Is #2357 already known in the product tracker? Not searchable without
  an account.

## Draft comment text

> (for #2341) Data point from a node where the unit does not fail:
> 4.22.0-okd-scos.10, single node, agent-based install, one internal NTP
> server set through (mechanism). `systemctl --failed` is empty after
> (N) reboots. `chronyc sources` at boot + 30 s: (output). Time source
> configuration: (snippet). Happy to run other checks on this node if it
> helps to find the difference.
