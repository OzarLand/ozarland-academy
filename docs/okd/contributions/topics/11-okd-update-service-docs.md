---
title: "11 — OKD: a 4.22 cluster says \"No updates available\" while a path to 5.0 exists; the project FAQ still describes the old update source"
description: "Since September 2026 OKD has its own update service (updates.okd.io, channels stable-5.0 and candidate-5.0)."
---

# 11 — OKD: a 4.22 cluster says "No updates available" while a path to 5.0 exists; the project FAQ still describes the old update source

- **Target:** `okd-project/okd-web` (the source of the project web
  site), branch `main`; possibly a data point on issue #2331 of
  `okd-project/okd`
- **Type:** documentation (FAQ refresh and an upgrade note)
- **Effort:** small
- **Status:** candidate, good confidence on the facts (graphs read
  directly); the switch of update service itself was **not** tested on
  the lab
- **Upstream state checked on:** 2026-11-13

## Summary

Since September 2026 OKD has its own update service
(`updates.okd.io`, channels `stable-5.0` and `candidate-5.0`). A cluster
installed with 4.22 keeps the previous settings: the release controller
as update source and the channel `stable-scos-4`. With those settings
`oc adm upgrade` answers "No updates available", although the new
service offers updates from `4.22.0-okd-scos.10` to several 5.0 builds.

The only place that explains the new service is a blog post. The FAQ of
the web site still sends readers to the release controller to "find
upgrades", and the "upgrade notes" section stops at the 4.15 to 4.16
move. An operator on 4.22 has no documentation page that says: change
the update source and the channel, then update.

## Why it matters in production

- "No updates available" on a cluster that is one major version behind
  reads as "nothing to do". It hides both the path to 5.0 and the fact
  that the cluster will not be offered fixes.
- The update source is a cluster-wide setting that an operator does not
  change without a written procedure.
- The lab's own upgrade page reached the wrong conclusion from the same
  output ("no edge starting from this version"), which shows how easy
  the trap is.

## Evidence from the lab

Lab: OKD `4.22.0-okd-scos.10`, single node, installed on 2026-11-11 with
the agent-based installer.

- `oc adm upgrade` on 2026-11-12, recorded in the lab's
  [OKD upgrade page](../../docs/lifecycle/07-okd-upgrade.md): upstream
  `https://amd64.origin.releases.ci.openshift.org/graph`, channel
  `stable-scos-4`, "No updates available", `status.availableUpdates`
  null.
- Graphs read directly on 2026-11-13 (HTTP GET from a workstation, not
  from the cluster):

  | Service | Channel | Updates offered from `4.22.0-okd-scos.10` |
  | --- | --- | --- |
  | release controller | `stable-scos-4` | none |
  | release controller | `stable-scos-5` | `5.0.0-okd-scos.0` to `.6` |
  | `updates.okd.io` | `stable-5.0` | `5.0.0-okd-scos.2` to `.6`, plus one conditional update |
  | `updates.okd.io` | `stable-scos-4` | empty graph |

**Not verified on the lab:**

- The cluster was **not** pointed at the new service; what
  `oc adm upgrade` shows afterwards on 4.22 is deduced from the graph,
  not observed.
- No update to 5.0 was run. The OpenStack operators of the lab are not
  validated on 5.0, which is a separate question.
- The conditional update and its risk text were not read.

## Upstream state

Looked at on 2026-11-13. `okd-project/okd-web` `main` at
`749fc3abcd70cebd429aea5a076325983dfbcee0`.

| Fact | Pointer |
| --- | --- |
| Announcement of the new service, channels, and the command to switch; says "first upgrade to 5.0.0-okd-scos.0, then set your cluster's upstream" | `blog/2026/09-18-okd-cincinnati.md` (pull request #120 of `okd-web`, merged 2026-09-22) |
| FAQ "Where can I find upgrades?" and "How can I upgrade my cluster" point to the release controller only | [`docs/project/faq.md` L59-L94](https://github.com/okd-project/okd-web/blob/749fc3abcd70cebd429aea5a076325983dfbcee0/docs/project/faq.md#L59-L94); the file has one commit, the initial import of 2024-04-01 |
| FAQ still describes single-node support in terms of the 4.7 installer | same file, L25-L29 |
| Upgrade notes exist only for 4.15 to 4.16 | `docs/project/upgrade-notes/` |
| Installer default for new clusters changed on `main` | `openshift/installer` pull request #10834 "Add OKD cincinnati as the default update service for OKD", merged 2026-09-25 |
| Open report about the channel on 5.0 clusters; a maintainer gives the switch command there | `okd-project/okd` issue #2331 (open, last comment 2026-10-05) |
| Blocked updates are declared in | `okd-project/cincinnati-graph-data` (`blocked-edges/`, `channels/`) |

Duplicate search on 2026-11-13: `okd-project/okd-web` issues and pull
requests, open and closed, for "cincinnati" (#120 only), "upgrade
channel" (dependency updates only), "stable-scos" (nothing about the
FAQ); the nine open pull requests were listed, none touches the FAQ
upgrade section or the upgrade notes. `okd-project/okd` for
"updates.okd.io" (#2331 only) and "No updates available" (13 results,
none about the documentation).

**Not specific to the lab:** every cluster installed with a 4.22
installer has these defaults.

The product documentation site built from `openshift/openshift-docs` is
not a possible target: that repository states that it does not accept
outside contributions for now (see the methodology).

## Proposed contribution

One pull request to `okd-web`:

1. FAQ: rewrite "Where can I find upgrades?" and "How can I upgrade my
   cluster to a new version?" around the update service, keep the release
   controller as the place to read release contents.
2. New upgrade note "from 4.22 to 5.0": the default settings of a 4.22
   cluster, why it shows no update, the command to switch (quoted from
   the blog post and the issue), how to read a conditional update.

Before writing, settle the one point where sources disagree: the blog
says to update to `5.0.0-okd-scos.0` first and switch afterwards; the
graph of the new service offers updates from 4.22 directly. Ask on
issue #2331 or in the project's discussion channel which order the
maintainers recommend, and write that.

## Reproduction and validation plan

1. `[READ-ONLY]` `oc get clusterversion version -o jsonpath='{.spec.upstream} {.spec.channel}'`
   and `oc adm upgrade` (already recorded).
2. `[READ-ONLY]` Read the graphs again on the day of the pull request:
   `curl -s -H 'Accept: application/json' 'https://updates.okd.io/api/updates/graph?channel=stable-5.0&arch=amd64'`.
3. `[CHANGE]` On a disposable 4.22 cluster (or the lab, with a snapshot
   and the owner's decision): patch `spec.upstream` and `spec.channel`,
   capture `oc adm upgrade`. This changes no workload but is a
   cluster-wide setting; revert by patching the old values back.
4. `[DESTRUCTIVE]` Optional and only on a disposable cluster: run the
   update to 5.0 and note what the page should warn about.
5. Build the site locally (`npm install`, `npm run build`, Node 18 or
   later per the repository README) and read the pages.

## Effort and risk

- A few hours once the recommended order is known.
- Review latency is the main risk: outside pull requests on `okd-web`
  have waited from days to months (#99: 11 days, #103: 21 days; #107
  and #111 open since April and May 2026). Keep the change
  small and announce it where the maintainers talk.
- Low technical risk: documentation only, commands quoted from the
  project's own post.

## Review-readiness checklist

- [ ] Recommended order confirmed by a maintainer (link in the pull
      request)
- [ ] Step 3 done on a 4.22 cluster, real output in the page
- [ ] Graph facts re-read on the day
- [ ] Site builds locally; the repository's pull request build check
      passes
- [ ] No statement about 5.0 behaviour that was not observed

## Open questions

- Will a later 4.22 build change the defaults of existing clusters, which
  would make the note obsolete? Read the cluster-version operator change
  mentioned in the blog post (#1466) first.
- Does the documentation site `docs.okd.io` describe the new service
  anywhere? Not checked page by page.

## Draft pull request text

> **Title:** docs: describe the OKD update service in the FAQ and add a
> 4.22 to 5.0 upgrade note
>
> The FAQ still points to the release controller as the place to find
> upgrades. Clusters installed with 4.22 use it as update source with
> channel `stable-scos-4` and report "No updates available", while
> `updates.okd.io` offers updates to 5.0 on `stable-5.0`.
>
> This change updates the two FAQ answers and adds an upgrade note with
> the default settings of a 4.22 cluster, the command to switch (from the
> Cincinnati blog post) and the output to expect. The order of
> operations follows (link to the maintainer's answer).
>
> Tested: settings switched on a 4.22.0-okd-scos.10 single-node cluster,
> output included; site built locally.
