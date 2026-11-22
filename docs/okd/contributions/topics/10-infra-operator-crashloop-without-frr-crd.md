---
title: "10 — infra-operator crash-loops when the FRRConfiguration resource type is not installed"
description: "The infra-operator contains a controller for BGP (BGPConfiguration) that watches FRRConfiguration objects of the frr-k8s project."
seo_title: "10 — infra-operator crash-loops without FRR CRD"
---

# 10 — infra-operator crash-loops when the `FRRConfiguration` resource type is not installed

- **Target:** `openstack-k8s-operators/infra-operator`, branch `main`
- **Type:** robustness fix (Go, controller set-up) or, at least, a
  documented prerequisite
- **Effort:** small (a guarded watch, following a pattern the same
  repository already uses twice) + a test
- **Status:** candidate — crash-loop observed once on the lab at
  18-stable; unconditional watch read on `main`; whether the maintainers
  consider a cluster without that resource type supported is unknown
- **Upstream state checked on:** 2026-11-13

## Summary

The infra-operator contains a controller for BGP (`BGPConfiguration`)
that watches `FRRConfiguration` objects of the `frr-k8s` project. The
watch is registered unconditionally when the operator starts. On a
cluster where MetalLB is installed without `frr-k8s` (layer 2 mode, no
BGP), the resource type does not exist, the cache never synchronises and
the whole operator exits and restarts in a loop. Every other controller
of the infra-operator (DNS, IP sets, memcached, RabbitMQ, Redis) is down
with it, although none of them needs BGP.

The same repository already protects two other optional watches with a
check of the REST mapper. Applying the pattern to the BGP controller
would make the operator start on any cluster and only enable BGP where it
can work.

## Why it matters in production

- An operator that dies because an optional integration is absent takes
  the control plane's DNS, messaging and cache management with it. The
  log line names a cache, not the missing prerequisite.
- The MetalLB operator shipped with the commercial distribution installs
  the resource type, so the problem is invisible there. It appears on
  community clusters and on any cluster where MetalLB comes from the
  upstream manifests or chart without the `frr-k8s` part.
- Layer 2 only deployments are common in small production sites.

## Evidence from the lab

Lab: OKD 4.22, MetalLB v0.16.2 from the upstream manifest
(`metallb-native.yaml`), `openstack-operator.v0.8.0` (18-stable catalog).

- Validation log, section "Platform services" (2026-11-11): the
  infra-operator crash-looped with
  `failed to wait for bgpconfiguration caches to sync kind source: *v1beta1.FRRConfiguration`.
- Fix applied by the lab: install only the
  `frrconfigurations.frrk8s.metallb.io` definition, without the daemon
  (`scripts/bastion/04-platform-services.sh`). The operator has been
  stable since.
- Read on 2026-11-13: the definition is present on the lab; no
  `BGPConfiguration` object is used.

**Not verified on the lab:**

- The crash-loop was seen once during the first installation; the pod
  log of that moment was not kept beyond the line quoted above.
- Not tried against a build of `main`.
- Whether other operators of the set have the same kind of hard
  dependency was not checked systematically.

## Upstream state

Looked at on 2026-11-13, `main` at `12c94c172a56d37dce95ed84599e085d43a9202b`.

| Fact | Pointer |
| --- | --- |
| Unconditional watch on `FRRConfiguration` | [`internal/controller/network/bgpconfiguration_controller.go` L356-L366](https://github.com/openstack-k8s-operators/infra-operator/blob/12c94c172a56d37dce95ed84599e085d43a9202b/internal/controller/network/bgpconfiguration_controller.go#L356-L366) |
| The controller is always set up; a failure exits the process | `cmd/main.go` L339-L346 |
| Guarded watch on an optional resource type (the pattern to reuse) | `internal/controller/instanceha/instanceha_controller.go` L872-L879 and `internal/controller/rabbitmq/transporturl_controller.go` L930 (`mgr.GetRESTMapper().RESTMapping(...)` before `Watches`) |
| BGP controller introduced by | pull request #322 "[bgp] Add new CRD to manage FRRConfiguration", closed 2024-12-02 |
| No mention of `frr-k8s` as a prerequisite | `README.md` and `docs/` of the repository: no match for "frr" |

Duplicate search on 2026-11-13 in
`openstack-k8s-operators/infra-operator` (issues and pull requests, open
and closed): "failed to wait for bgpconfiguration caches" (0), "no
matches for kind FRRConfiguration" (0), "FRRConfiguration crd" (two
results, #322 and #333, unrelated to the crash), "crashloop" (0). Jira (project OSPRH)
could not be searched.

**Partly specific to the lab:** the trigger is a MetalLB installed
without the MetalLB operator, which is not the documented way on the
commercial distribution. On OKD 4.22 the default community catalog does
not offer the MetalLB operator (see
[topic 12](12-install-yamls-okd-path-outdated.md)), so community users
are pushed towards the manifests. The missing guard itself is in the
code for everyone.

## Proposed contribution

1. A short issue: observed behaviour, the two existing guarded watches as
   precedent, and the question "is a cluster without `frr-k8s` supported;
   would you take a guard?".
2. If yes, a pull request: in `SetupWithManager`, register the
   `FRRConfiguration` watch only when the REST mapper knows the kind, and
   make the reconcile function return a clear condition ("frr-k8s not
   installed") when a `BGPConfiguration` object exists without it.
3. If the answer is "not supported", a one-paragraph prerequisite in the
   documentation is still worth a pull request.

Known limit to state in the issue: a guard evaluated at start-up does
not notice a definition installed later; the operator must be restarted.
The two existing guards have the same limit.

## Reproduction and validation plan

1. `[READ-ONLY]` `oc get crd frrconfigurations.frrk8s.metallb.io` and
   `oc get bgpconfiguration -A` to record the starting state.
2. `[DESTRUCTIVE]` On a disposable cluster (not the long-running lab):
   delete the definition, restart the infra-operator pod, capture the log
   and the restart count. Deleting a definition deletes its objects; this
   is why the step is not for the shared lab.
3. `[CHANGE]` Run a patched operator image on the same cluster: the
   operator must start, DNS and RabbitMQ resources must reconcile.
4. `[CHANGE]` Install the definition, restart the operator, create a
   `BGPConfiguration`: behaviour unchanged from today.
5. Unit and functional tests: `make test` in the repository; add an
   envtest case that starts the manager without the definition if the
   test set-up allows removing it.

## Effort and risk

- Code: about ten lines plus a condition message.
- Risk: the maintainers may answer that the resource type is a hard
  prerequisite and prefer documentation. Both outcomes are acceptable.
- Risk of duplicate in Jira: unknown.

## Review-readiness checklist

- [ ] Crash-loop reproduced on a disposable cluster, log captured
- [ ] Behaviour confirmed on a build of `main`
- [ ] Issue answered by a maintainer before any code is sent
- [ ] Patched image tested with and without the definition
- [ ] `make test` and the linters of the repository pass locally
- [ ] Commit message explains the start-up-only limit

## Open questions

- Is the envtest environment of the repository able to start without one
  of the external definitions it loads?
- Should the guard also cover the RBAC marker and the scheme
  registration, or only the watch?

## Draft issue text

> **Title:** infra-operator exits in a loop when the FRRConfiguration
> CRD is not installed (MetalLB without frr-k8s)
>
> **Environment:** OKD 4.22, MetalLB v0.16.2 installed from the upstream
> manifests in layer 2 mode (no frr-k8s), infra-operator from the
> 18-stable catalog. Code read on `main` at `12c94c17`: same set-up.
>
> **What happened:** the operator restarts in a loop with
> `failed to wait for bgpconfiguration caches to sync kind source: *v1beta1.FRRConfiguration`.
> No BGPConfiguration object exists. All controllers of the operator are
> down with it.
>
> **Workaround:** install the `frrconfigurations.frrk8s.metallb.io` CRD
> alone.
>
> **Question:** `instanceha` and `transporturl` controllers already
> guard their optional NodeSet watch with a REST mapper check. Would you
> accept the same guard for the FRRConfiguration watch, or is frr-k8s a
> hard prerequisite that should be documented? I can send either change.
