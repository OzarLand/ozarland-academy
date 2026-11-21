---
title: "06 — Data plane agent health checks: the metadata check can pass while the agent is cut off, and nothing acts on \"unhealthy\""
description: "06 — Data plane agent health checks: the metadata check can pass while the agent is cut off, and nothing acts on \"unhealthy\""
---

# 06 — Data plane agent health checks: the metadata check can pass while the agent is cut off, and nothing acts on "unhealthy"

- **Target:** `openstack-k8s-operators/edpm-ansible`, branch `main`
- **Type:** test report on a new feature, then a small script or
  documentation change if the maintainers want one
- **Effort:** small for the report; small to medium for a change
- **Status:** candidate, lower confidence — the "healthy while cut off"
  state was observed on the lab with the **previous** health check; for
  the new script (merged 2026-11-05) it is a reading of the code, not a
  test
- **Upstream state checked on:** 2026-11-13

## Summary

Two related observations about the container health checks of the data
plane agents:

1. The new health check of the OVN metadata agent opens a **new**
   connection to the southbound database with `ovsdb-client`. It proves
   that the database is reachable from the container, not that the
   agent's own connection is alive. In the failure of
   [topic 05](05-ovn-agents-stuck-after-dns-outage.md) the agent is stuck
   while a fresh process connects without trouble, so the check would
   stay green. The `ovn-controller` check does not have this weakness: it
   asks the daemon itself (`connection-status`).
2. When a check does fail, the container is marked `unhealthy` and that
   is all. The units restart on process exit (`Restart=always`), not on
   health status, and no alerting hook is described. On the lab
   `ovn_controller` stayed `unhealthy` for as long as it was
   disconnected (8 to 15 minutes, see topic 05) and nothing reacted.

## Why it matters in production

- A health check that is green while the agent is disconnected is worse
  than none for whoever builds monitoring on `podman ps` or on the
  node exporter's container metrics.
- Operators need to know what "unhealthy" is meant to trigger. If the
  answer is "nothing, alert on it yourself", the documentation should say
  so and give the metric to watch.

## Evidence from the lab

Lab collection: 18-stable before the new health check scripts.

- 2026-11-12: `ovn_controller Up 18 hours (unhealthy)`, error
  `ERROR - OVN-Controller is not connected to OVN SB database`; no
  restart happened by itself. The 18 hours are the age of the
  container: the journal, re-read on 2026-11-14, shows the controller
  disconnected for 9 min 28 s when it was restarted by hand. An
  earlier version of this page read it as 18 hours of `unhealthy`.
- 2026-11-14, start of the whole lab, agents left alone:
  `ovn_controller` was `unhealthy` from 07:39:38 until it reconnected
  by itself at 07:53:10 UTC, then `healthy` again; `NRestarts=0`.
  `ovn_metadata_agent` was disconnected until 07:54:29 and never left
  `healthy`: the check deployed on the lab is a script that only runs
  `true` (read in the container on 2026-11-14).
- Same day, after a second control-plane restart:
  `ovn_controller Up 9 minutes (unhealthy)` and
  `ovn_metadata_agent Up 8 minutes (healthy)` while the metadata agent
  could not reach the southbound database (agent reported dead about
  75 s after the next northbound change).
- Source: the lab evidence files `kb4/14-roll1-after.txt` and
  `kb4/21-roll2-timeline.txt`, summarised in
  [the knowledge base](../../docs/knowledge-base/okd-node-maintenance.md#why-are-the-ovn-agents-of-the-compute-node-dead-after-a-reboot-of-the-okd-node-and-how-do-i-fix-them).

**Not verified on the lab:**

- The new metadata health check was never run on the lab. Point 1 is an
  inference from the script.
- Whether the previous metadata check and the new one differ on this
  point was not compared in detail.

## Upstream state

Looked at on 2026-11-13, `main` at `3e5e2930038443693cecd21caab5a50db051d93a`.

| Fact | Pointer |
| --- | --- |
| Metadata check: `ovsdb-client ... get-schema "$sb_remote" OVN_Southbound` | [`roles/edpm_neutron_metadata/files/healthchecks/ovn_metadata_agent/healthcheck` L82-L84](https://github.com/openstack-k8s-operators/edpm-ansible/blob/3e5e2930038443693cecd21caab5a50db051d93a/roles/edpm_neutron_metadata/files/healthchecks/ovn_metadata_agent/healthcheck#L82-L84) |
| Controller check asks the daemon: `ovn-appctl -t ovn-controller connection-status` | `roles/edpm_ovn/files/healthchecks/ovn_controller/healthcheck` |
| Health options of the unit: command, interval, timeout, retries; `Restart=always`; no `--health-on-failure` | `roles/edpm_neutron_metadata/templates/quadlet/ovn_metadata_agent.container.j2` L31-L34 and L47; `roles/edpm_ovn/templates/quadlet/ovn_controller.container.j2` L41-L48 |
| No `health-on-failure` or `HealthOnFailure` anywhere in the repository | `git grep -i` on the commit above: no match |
| New scripts come from | pull request #1345 (merged 2026-11-05, Jira OSPRH-39282), copied to `18-stable` by #1350 (merged 2026-11-12) |

Duplicate search on 2026-11-13 in `openstack-k8s-operators/edpm-ansible`
(issues and pull requests, open and closed): "health-on-failure" (0),
"healthcheck restart unhealthy" (0), "unhealthy" (2, both
unrelated: #995, #170). The review discussion of #1345 was skimmed, not read in full: the
choice of a new connection may have been discussed there or in Jira.

**Not specific to the lab.**

## Proposed contribution

1. Run the failure of topic 05 with the new scripts and report what each
   check says while the agent is cut off. If the metadata check stays
   green, open an issue with the timeline.
2. Ask, in the same issue, what `unhealthy` is expected to trigger. Do
   not propose automatic restarts as a pull request: restarting network
   agents on a health signal is a design decision with a history, and it
   is the maintainers' to take.
3. If they agree, a documentation paragraph ("what the health checks
   cover, what they do not, what to alert on") is a small, safe first
   pull request.

## Reproduction and validation plan

1. `[CHANGE]` Deploy a collection that contains #1350 on the lab node.
2. `[CHANGE]` Reproduce the DNS outage of topic 05.
3. `[READ-ONLY]` Every minute: `podman ps --format '{{.Names}} {{.Status}}'`,
   `podman healthcheck run ovn_metadata_agent; echo $?`,
   `ovn-appctl connection-status`, and the Neutron agent list after one
   northbound change.
4. `[READ-ONLY]` `systemctl show edpm_ovn_controller -p NRestarts` before
   and after, to prove that no restart was triggered.

## Effort and risk

- Rides on the test of topic 05; one more hour.
- Risk: criticising a change merged a week ago by a core developer of
  the area. Keep it to observed facts and a question.

## Review-readiness checklist

- [ ] Topic 05 reproduction done with the new scripts
- [ ] Timeline of check results against real agent state
- [ ] Review discussion of #1345 read in full
- [ ] Issue written as a test report, not as a design proposal

## Open questions

- Is there a cheap way for the script to test the agent's own
  connection (the metadata agent has no control socket like
  `ovn-controller`)? One idea to check, not to propose blindly: compare
  the `nb_cfg` the agent writes in `Chassis_Private` with the global
  one.
- Does the node exporter or another shipped component already export
  container health for alerting?

## Draft issue text

> **Title:** ovn_metadata_agent health check stays healthy while the
> agent has lost its southbound connection
>
> **Version:** edpm-ansible at (commit), health checks from #1345.
>
> **Test:** (timeline: DNS outage, agent state, result of
> `podman healthcheck run` each minute)
>
> **Observation:** the check opens its own connection with
> `ovsdb-client get-schema`, which succeeds, while the agent process
> keeps failing. `ovn_controller` is correctly reported unhealthy for
> as long as it is disconnected, and nothing reacts to it.
>
> **Questions:** is the check meant to cover the agent's own connection?
> What is the intended reaction to an unhealthy agent container: alert
> only? I can send a documentation change with the answer.
