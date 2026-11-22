---
title: "12 — The OKD=true path of install_yamls dates from 2023; a report from OKD 4.22 on what still works"
description: "Contribution proposal for a test report on the OKD switch of install_yamls, listing what the lab found on OKD 4.22 for the three platform prerequisites."
seo_title: "12 — The OKD path of install_yamls is outdated"
---

# 12 — The `OKD=true` path of install_yamls dates from 2023; a report from OKD 4.22 on what still works

- **Target:** `openstack-k8s-operators/install_yamls`, branch `main`
- **Type:** test report first; then small fixes or a README section,
  depending on the answer
- **Effort:** medium (one disposable OKD cluster, the three `make`
  targets, notes)
- **Status:** candidate — the path was read, **not run**; the lab was
  built with its own scripts. One prerequisite of the path was checked
  read-only on the lab
- **Upstream state checked on:** 2026-11-13

## Summary

install_yamls, the developer deployment tool of the operators, has an
`OKD=true` switch that replaces the three platform prerequisites taken
from the commercial catalog (NMState, MetalLB, cert-manager) by community
sources. The switch was added in December 2023 and last touched in June
2024. Its README section is two lines long. An outside pull request that
fixes its MetalLB part has been open since April 2025 without having
been admitted to testing.

The lab runs the same operators on OKD 4.22 and solved the same three
prerequisites differently. That makes its owner one of the few people
who can say, with evidence, what a community user meets today: which
catalog exists by default, what it contains, what breaks. A factual
report, followed by whatever small change the maintainers ask for, is a
contribution nobody inside the team is placed to make.

## Why it matters in production

- Not a production topic by itself: install_yamls is a development
  tool. It matters because it is the documented entry point for anyone
  evaluating the operators on the community distribution, and because
  the people who maintain it are the ones whose trust is sought.
- It is also the natural home for the knowledge the lab accumulated
  about prerequisites on OKD (see [topic 10](10-infra-operator-crashloop-without-frr-crd.md)).

## Evidence from the lab

Lab: OKD `4.22.0-okd-scos.10`. Read on 2026-11-13:

- Catalog sources: only `community-operators`
  (`community-operator-index:v4.22`, 319 packages) besides the lab's own
  OpenStack catalog.
- Packages matching the prerequisites in that catalog: `cert-manager`
  (default channel `stable`) is present; there is **no** MetalLB operator
  and **no** NMState operator package.
- What the lab does instead (its installation scripts and
  [platform services page](../../docs/installation/03-platform-services.md)):
  cert-manager and MetalLB from the upstream manifests with pinned
  versions, the `FRRConfiguration` definition added by hand, no NMState
  operator (the node network is configured at installation time).

**Not verified on the lab:**

- `make nmstate`, `make metallb`, `make certmanager` and
  `make openstack` with `OKD=true` were never run. Nothing in this topic
  says they fail.
- Whether the catalog image `quay.io/operatorhubio/catalog:latest` that
  the MetalLB step adds still serves a MetalLB operator that works on
  OKD 4.22 was not checked.

## Upstream state

Looked at on 2026-11-13, `main` at `ebca8c46528d222741c42abfc4e31bafd1ec879c`.

| Fact | Pointer |
| --- | --- |
| README section "Deployment on OKD distro": one sentence and `make openstack OKD=true` | [`README.md` L241-L247](https://github.com/openstack-k8s-operators/install_yamls/blob/ebca8c46528d222741c42abfc4e31bafd1ec879c/README.md#L241-L247) |
| NMState on OKD: operator manifests downloaded from the project's GitHub release, default version `v0.81.0` | `Makefile` L2473-L2478, `scripts/gen-olm-nmstate-okd.sh` |
| MetalLB on OKD: adds a catalog source `operatorhubio-catalog` (image tag `latest`), subscribes to `metallb-operator`, channel `beta` | `Makefile` L2601-L2611, `scripts/gen-operatorshub-catalog.sh`, `scripts/gen-olm-metallb-okd.sh` |
| cert-manager on OKD: package `cert-manager` from `community-operators`, channel `stable` | `Makefile` L3024-L3026, `scripts/gen-olm-cert-manager-okd.sh` |
| Marketplace validation on OKD only checks cert-manager | `scripts/validate-marketplace-okd.sh` |
| History of the path | pull requests #648 (2023-12-01), #670, #688, #815, #820, #833, #849 (2024-06-10); commit list of `scripts/gen-olm-metallb-okd.sh` ends on 2024-01-12 |
| Outside fix waiting | pull request #1055 "Fix issues with metallb on OKD", opened 2025-04-29, three files, still labelled as needing a member's approval to run tests on 2026-11-13 |
| NMState on OKD today comes from a separate community catalog, with an open problem | `okd-project/okd` issue #2374 (closed 2026-10-23) and the issue it links in `okd-project/okderators-catalog-index` |

Duplicate search on 2026-11-13 in
`openstack-k8s-operators/install_yamls` (issues and pull requests, open
and closed): "OKD" (10 results, listed above, plus #1029 and #1177
unrelated), "operatorhubio" (0). No recent report on the state of the
path.

**Not specific to the lab.**

## Proposed contribution

1. Run the path as written on a disposable OKD 4.22 cluster and write
   down, target by target, what happens.
2. Publish the result as an issue: versions, outputs, and for each
   failure the smallest change that fixes it. Mention #1055 and say
   whether it is still needed and still applies; do not take it over
   without its author.
3. Depending on the answer: a README section that states the tested OKD
   version and the prerequisites, or fixes to the scripts, one pull
   request per target.

Do not propose replacing the path by the lab's approach. Offer the facts
and let the maintainers choose.

## Reproduction and validation plan

1. `[CHANGE]` Create a disposable OKD 4.22 cluster (a second single-node
   install; the long-running lab must not be used, the targets install
   operators cluster-wide).
2. `[CHANGE]` `make nmstate OKD=true`, `make metallb OKD=true`,
   `make certmanager OKD=true`, then `make openstack OKD=true`; keep the
   full output and `oc get csv,subscription,catalogsource -A` after each.
3. `[READ-ONLY]` For each prerequisite, record the version that ended up
   running and the catalog it came from.
4. `[CHANGE]` Apply #1055 locally and repeat the MetalLB step.
5. `[DESTRUCTIVE]` Delete the disposable cluster.

## Effort and risk

- One to two days, mostly cluster time.
- Risk: the maintainers may consider the path unmaintained and remove
  it. That is still a useful outcome, and the report then becomes the
  argument for a "community distribution" page elsewhere.
- Risk of low interest: the open pull request shows that OKD changes can
  wait a long time. Ask in the team's channel before investing the two
  days.

## Review-readiness checklist

- [ ] Interest confirmed by a maintainer
- [ ] Path run unmodified, outputs kept
- [ ] Each proposed fix tested alone
- [ ] Author of #1055 contacted or credited
- [ ] Report free of any detail of the hosting environment

## Open questions

- Is any CI job running `OKD=true`? None was found in the repository
  (search for "OKD" in the Zuul and workflow files), which was not an
  exhaustive check of the external CI definitions.
- Does the team want OKD knowledge in install_yamls, in the developer
  documentation repository, or nowhere?

## Draft issue text

> **Title:** State of the OKD=true path on OKD 4.22: test report
>
> I run the 18-stable operators on OKD 4.22 (single node) and tried the
> `OKD=true` targets on a fresh cluster.
>
> **Catalogs on a default OKD 4.22:** only `community-operators`
> (v4.22); it has `cert-manager` but no MetalLB and no NMState operator.
>
> **Results:** (one paragraph per target: command, outcome, versions)
>
> **Related:** #1055 (status after my test: ...).
>
> **Proposal:** (README update with the tested version / the following
> small fixes). Tell me which you prefer and I will send it.
