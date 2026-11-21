---
title: "15. The specialised workshops"
description: "Four more workshops build whole quarters, share visitors, keep the keys and name the streets: Heat, Octavia, Barbican and Designate."
---

# 15. The specialised workshops

*The gallery of additional services.*

<img src="assets/images/S15-open.webp" width="1536" height="1024" alt="LUMO presents four small workshops side by side: linked tiles, a balance, a locked chest and a set of rings.">

At the end of the main street, four smaller workshops stand side by side. Not every village has all of them; this
one does.

Aster lays tiles on a table, linked by threads: two houses, a road, a bridge, a public number. "Give me the plan, and I
build the whole quarter in the right order, and take it down the same way." Farah stands at a switch with several
tracks: "When one house is not enough, I send each visitor to one of several houses, and I stop sending them to a house
that doesn't answer." Taro keeps a sealed box: certificates and passwords that services need but nobody should leave
lying around. Ina hangs name rings on posts: visitors can ask for `shop.neri.example` instead of a number.

<img src="assets/images/S15-v1.webp" width="1024" height="1024" loading="lazy" alt="On a parchment lie four objects: linked tiles, a forked track, a small locked chest and nested rings.">

LUMO looks at each in turn and does not mix them up: four tools, four jobs.

<img src="assets/images/S15-v2.webp" width="1024" height="1024" loading="lazy" alt="A brass dome with a cloud sends three golden arrows to three identical servers on a map.">

> [!IMPORTANT]
> **Where the picture stops.** These services are optional. Whether a cloud offers them, and how they behave, depends
> on what the operators enabled, the plugins and back ends they chose, and the policies they set.

## What it is in OpenStack

- **Heat** is orchestration: a **template** (HOT, in YAML) describes a set of linked resources, a **stack**, that Heat
  creates, updates and deletes together, in dependency order.
- **Octavia** is load balancing as a service: a **load balancer** with **listeners** and **pools** of **members**,
  with health monitors that take failing members out.
- **Barbican** is the key manager: it stores **secrets** (keys, certificates, passphrases) and controls who may read
  them. Other services, such as Octavia for TLS or Cinder for encrypted volumes, use it.
- **Designate** is DNS as a service: **zones** and **record sets** that it publishes to real DNS servers.

## From the village to OpenStack

```mermaid
flowchart TB
    T["Heat template"] -->|"creates as one stack"| ST["Stack: 2 VMs + network + LB"]
    C["Client"] -->|"HTTPS"| LB["Octavia load balancer"]
    LB --> M1["Member: VM 1"]
    LB --> M2["Member: VM 2"]
    BB[("Barbican<br/>TLS certificate")] -.->|"read by the listener"| LB
    DS["Designate zone<br/>shop.neri.example → LB address"] -.->|"DNS answer"| C
```

## See it for real

Each command needs the service on the cloud and its plugin in the `openstack` client:

```bash
openstack stack list
openstack loadbalancer list
openstack secret list
openstack zone list
```

**The lantern:** four small beams pick out four different tools without merging them.

**Next:** LUMO climbs to the lookout to see the village as a whole.
[16. The village runs. What now? →](16-the-village-runs.md)
