---
title: "16. The village runs. What now?"
description: "From the lookout LUMO sees regions and availability zones, prepares a careful exercise with Neri as a storm is announced, and takes the road to the Quick lab."
remember:
- "A <strong>region</strong> is a separate deployment with its own endpoints, often in another place; Keystone is usually shared."
- "An <strong>availability zone</strong> is a group of hosts inside a region, defined by the operators."
- "A name does not prove resilience: look at the real architecture and test it, starting in a lab."
quiz:
- q: "Two availability zones named <code>north</code> and <code>south</code>: do they fail independently?"
  options:
  - "Yes, that is what an AZ guarantees"
  - "Only if their power, network and storage were built independently"
  answer: 1
  explain: "An AZ is a grouping chosen by the operators; independence comes from the design, not from the label."
  see: "what-it-is-in-openstack"
- q: "Where can you see the regions of a cloud?"
  options:
  - "<code>openstack region list</code> and the endpoints of the catalog"
  - "<code>openstack flavor list</code>"
  answer: 0
  explain: "Each region has its own set of endpoints in the catalog."
  see: "see-it-for-real"
---

# 16. The village runs. What now?

*The lookout above the archipelago.*

<img src="assets/images/S16-open.webp" width="1536" height="1024" alt="Neri and LUMO stand at the lookout above the harbour, with clouds gathering far out at sea.">

From the lookout the whole village is visible: the town hall, the workshops on their terraces, the roads, the bridge,
the storerooms. Far across the water, another village with its own town hall serves the next island. On the terraces
below, the workshops are grouped in quarters, each with its own water supply and its own path down to the quay.

"So if one quarter loses its water, the houses in another quarter keep going?" Neri asks. LUMO hesitates. "Only if
the quarters were really built that way. A name on a sign doesn't tell you. You have to look at how they were built,
and test it."

<img src="assets/images/S16-v1.webp" width="1024" height="1024" loading="lazy" alt="From the lookout, Neri and LUMO look out over the island: the town hall and the quarters of the village below, separated by paths and gardens, and further out other islands, each with its own town hall.">

The sky darkens over the sea: a storm is announced for tomorrow. Nothing is broken, but Neri is worried. LUMO opens
the notebook. "Then let's practise. Not here, on the real houses. In a small village of our own, where we can break
things on purpose and learn to repair them."

The lantern is small, but steady. It lights the road down to the harbour.

<img src="assets/images/S16-v2.webp" width="1024" height="1024" loading="lazy" alt="At dusk, LUMO and Neri sit at a small table by the lantern and go through a blank checklist, with storm clouds far out over the sea.">

> [!IMPORTANT]
> **Where the picture stops.** The name of a region or an availability zone is not enough to know its topology or its
> resilience. An availability zone does not by itself guarantee high availability: you have to look at the real
> architecture and the real procedures, and test them.

## What it is in OpenStack

- A **region** is a separate OpenStack deployment with its own endpoints in the catalog, often in another location.
  Regions usually share Keystone; each has its own compute, network and storage services. You choose a region when you
  make a request.
- An **availability zone** (AZ) is a group of hosts inside a region that the operators define, ideally with
  independent power, network or racks. Users can ask for an instance in a given AZ. Compute, block storage and
  networks each have their own notion of AZ.
- High availability comes from the design and from how your service is spread and tested, not from the labels.

## From the village to OpenStack

```mermaid
flowchart TB
    K["Keystone (shared)<br/>catalog with one set of endpoints per region"]
    K --> R1
    K --> R2
    subgraph R1["Region: island-1"]
        AZ1["AZ: north<br/>hosts 1-10"]
        AZ2["AZ: south<br/>hosts 11-20"]
    end
    subgraph R2["Region: island-2"]
        AZ3["AZ: nova<br/>hosts 1-8"]
    end
```

Whether `north` and `south` fail independently depends on how their power, network and storage were built.

## See it for real

```bash
openstack region list
openstack endpoint list
openstack availability zone list --compute
```

In Horizon, the region selector is at the top of the page when the cloud has several regions.

**The lantern:** small but steady, it lights the road to the lab and to the archipelago.

## The road goes on

<img src="assets/images/S17-archipelago-exit.webp" width="1536" height="1024" loading="lazy" alt="On the harbour quay, LUMO points out to sea with an open hand while Neri, bedroll on the back, watches a sailing ship leave for the islands of the archipelago.">

The village answers its inhabitants. Now the question is: how do you break it and repair it safely? That is the next
stop: the [Quick lab](../lab/), a real, disposable OpenStack in about an hour, with exercises to break and repair it.

Further on, the book [*OpenStack, the Day After Tomorrow*](https://book.ozarland.com/) follows LUMO across the
archipelago, from a platform nobody fully understands to one a team can run for the long term.

[← Back to the village](index.md)
