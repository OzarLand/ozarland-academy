---
title: "Issue report template"
description: "A skeleton for a bug report or a documentation gap report sent to an upstream project."
---

# Issue report template

A skeleton for a bug report or a documentation gap report sent to an
upstream project. Copy the block below into the topic page first, fill it
there, validate it on the lab, and only then paste it into the upstream
tracker. If the project has its own issue template, its headings win: move
the content below under them and drop nothing.

Before filling it, read [the methodology](../methodology.md) for the
tracker each project really uses and the information it asks for.

```markdown
<!-- Title: one line, the component first, the observed behaviour second.
     Example: "edpm_bootstrap: package installation failure is ignored on
     CentOS Stream". No "urgent", no "broken", no exclamation mark. -->

### Summary

Two or three sentences: what happens, when, and the consequence for an
operator.

### Environment

- Project version: branch or tag, commit, bundle or image digest
- Kubernetes distribution and version
- Topology: number of control plane nodes, number of data plane nodes
- Deployment method: how the operators were installed
- Anything that differs from the reference deployment of the project
  (state it plainly: it is the first thing a maintainer needs to know)

### Steps to reproduce

1. Numbered, minimal, copy-pasteable commands.
2. Start from a state a maintainer can reach.
3. Say how many times the reproduction was run and how many times it
   showed the problem.

### Expected result

What should happen, and on what basis (documentation sentence, code
comment, behaviour of another component).

### Actual result

What happens. Exact messages in a code block, trimmed to the relevant
lines, with time stamps when ordering matters.

### Analysis (optional)

Only what has been checked. Give file paths and a commit for each code
reference. Separate clearly "verified" from "suspected".

### What was not tested

The limits of the report: versions not tried, topologies not available,
alternative explanations not ruled out.

### Workaround

The command that restores service, if one is known, and its side effects.

### Proposal (optional)

One proposed direction, and whether you are willing to send the change.
```

## Before sending

- [ ] Searched open **and closed** issues and pull requests, with the
      queries recorded in the topic page; no duplicate.
- [ ] Reproduced on the lab after the last relevant change, and the run is
      recorded in [the journal](../log.md).
- [ ] Checked whether the main branch still has the problem, by reading the
      code or by running it; the report says which.
- [ ] Every statement is either observed (with output) or marked as
      suspected.
- [ ] All addresses, host names, domain names, project names and
      credentials replaced by generic values (`lab.example.com`,
      `192.0.2.0/24`); attached logs checked line by line.
- [ ] The deviation from the supported or reference deployment is stated
      in the first screen of the report.
- [ ] The text is short enough to be read in two minutes; long output is
      attached, not inlined.
