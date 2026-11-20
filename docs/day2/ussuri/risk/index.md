---
title: Risk and impact
description: "Entry to the risk pages: the 25 rated risks, what a tag really executes, the tag index, and why a small change creates a large workload."
tags: [risk, tags, loop-notify, limit, scaling]
---

# Risk and impact

Potentially dangerous operations on a running Kolla-Ansible Ussuri platform, what a tag really executes, and why a small
change can create a large workload. Ratings are relative to a production cloud with running VMs.

## Start from

- **By operation:** the [Operations](../operations/index.md) catalogue has one row per operation page, with the risks
  that the page names.
- **By tag:** [Tags §3](tags.md#3-what-a-tag-really-executes-master-table) says what a tag executes, on which hosts, and
  which containers can restart. The [tag index](tag-index.md) goes from a tag to its component page.
- **By component:** [Components](../components/index.md) has one page per component; its "Where to look" section lists
  the risks of the component's tag when the study names some.
- **By severity:** the [summary table of the risk register](risk-register.md#matrix) gives the likelihood and the
  severity of each of the 25 risks.

## Pages

<div class="grid cards" markdown>

- **[Risk register](risk-register.md)** — 25 risks (R1–R25), each with what actually happens, its blast radius, VM and
  API impact, likelihood, severity, precautions and evidence.
- **[What a tag really executes](tags.md)** — How tags actually select work in Kolla-Ansible Ussuri, and what each
  important tag executes: on which hosts, and which containers can restart.
- **[Tag index](tag-index.md)** — One row per tag: the component page of the tag, or the full row for the three rows
  without a component page.
- **[Why a small change creates a large workload](small-change-large-workload.md)** — Six small changes, each with why
  it is large and its source, and the per-host work that every run pays.

</div>

## Related

- [Pre-execution checklist](../operations/pre-execution-checklist.md) — what to check before a run
- [Open questions](../troubleshooting/open-questions.md) — the open questions behind the [NOT AVAILABLE] cells of the
  risk register
- [Technical findings](../reference/findings.md) — the fifteen headline findings, each with its evidence
- [Conventions and evidence labels](../start/conventions.md#operation-impact-classes) — the impact classes shown on
  operation pages, among them `critical`
- [Compute scaling §5](../concepts/compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload) —
  the work multiplier and the restart multiplier
