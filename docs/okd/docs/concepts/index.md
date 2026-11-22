---
title: "Concepts"
description: "This guide explains how OpenStack is deployed and operated when Kubernetes operators manage its lifecycle."
---

# Concepts

<img src="../../assets/images/S6-compare.webp" width="1536" height="1024" loading="lazy" alt="Jo, holding a crate, LUMO and Kest stand behind two scale models of the same size: a timber workshop and a stone citadel with brass gears.">

> Status: aligned with the lab deployed on 2026-11-12 (OKD 4.22.0-okd-scos.10, operators 18-stable); explanatory page, commands spot-checked against the validated guides

This guide explains how OpenStack is deployed and operated when Kubernetes
operators manage its lifecycle. It is written for an engineer who already runs
OpenStack with Kolla-Ansible and is discovering Kubernetes and OKD.

Every Kubernetes concept is introduced through an OpenStack example that you
can look at in the lab, together with the `oc` command that shows it.

The one idea to take away: you no longer run a deployment tool. You declare
the platform in one object, `OpenStackControlPlane`, and programs called
operators keep the running services identical to it. **Write at the top,
read everywhere.**

## Lab baseline assumed by this guide

| Item | Value |
|---|---|
| Cluster | Single-node OKD (CentOS Stream CoreOS) |
| OpenStack operator | `openstack-operator`, branch `18-stable` |
| OpenStack services | Antelope (2023.1) container images |
| Data plane node OS | CentOS Stream 9 |
| Namespace of the operators | `openstack-operators` |
| Namespace of the OpenStack services | `openstack` |

- The control plane resource is named `openstack`, the data plane NodeSet
  `openstack-edpm`.
- The lab uses network isolation with one interface per network (machine,
  ctlplane, internalapi, tenant).
- It deploys a minimal set of services: Galera, RabbitMQ, Memcached, DNS,
  Keystone, Placement, Glance, Neutron with OVN, and Nova. Horizon, Cinder,
  Swift and the others are disabled by default (see
  [architecture](../architecture.md#software-layers)).
- `oc` runs on the bastion.
- Object names shown in examples are the ones observed on the deployed lab;
  the pages of the [operations guide](../operations/index.md) are the
  validated reference when a detail matters.

## Reading order

| # | Document | What you get from it |
|---|---|---|
| 1 | [From Kolla-Ansible to operators](01-from-kolla-to-operators.md) | A translation table between the two operating models |
| 2 | [Kubernetes building blocks](02-kubernetes-building-blocks.md) | Pod, Deployment, StatefulSet, Service, Secret, PVC... each seen on a real OpenStack service |
| 3 | [Operators, CRDs and reconciliation](03-operators-crds-and-reconciliation.md) | What an operator does, how a change to a custom resource reaches a running service |
| 4 | [Configuration, secrets and data](04-configuration-secrets-and-data.md) | Where `nova.conf` comes from, where passwords live, what is persistent |
| 5 | [Service lifecycle reference](05-service-lifecycle-reference.md) | One card per OpenStack service: operator, CRs, workload, storage, restart, scale |
| 6 | [Control plane and data plane](06-control-plane-and-data-plane.md) | What runs on OKD, what runs on compute nodes, and the networks between them |
| 7 | [OKD in brief](07-okd-in-brief.md) | Just enough OKD to operate OpenStack on it |

Documents 1 to 3 are enough to start the operational scenarios. Documents 4 to
6 are references you will return to. Document 7 is deliberately short: deeper
OKD administration is Phase 4 of the learning roadmap.

Each page opens with an "In short" block (what it explains and the ideas to
keep) and ends with links to the previous and next pages.

## Conventions

Commands are labelled so that you always know whether you are observing or
changing the platform:

- **[READ-ONLY]** commands (`oc get`, `oc describe`, `oc logs`,
  `openstack ... list`) are safe to run at any time.
- **[CHANGE]** commands (`oc apply`, `oc edit`, `oc patch`, `oc delete`)
  change the platform.
- **[DESTRUCTIVE]** commands can lose data or cause an outage that does not
  repair itself.

The label is on the line above each command block, as in the other guides.

Terminology used consistently across the repository:

| Term | Meaning |
|---|---|
| Control plane | The OpenStack API and infrastructure services running as pods on OKD |
| Data plane | The external nodes (compute nodes) configured by Ansible jobs launched from OKD |
| Custom resource (CR) | An object of a type added to the Kubernetes API by an operator |
| CRD | Custom Resource Definition: the schema that declares a CR type |
| Operator | A controller program running in the cluster that manages CRs of given types |
| Reconciliation | The loop in which an operator compares desired state (CR `spec`) with actual state and corrects the difference |

IP addresses in examples are the lab defaults (`192.168.122.0/24`,
`172.17.0.0/24`, `172.19.0.0/24`, `192.168.130.0/24`).
