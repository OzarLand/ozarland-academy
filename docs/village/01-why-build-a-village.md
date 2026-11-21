---
title: "1. Why build a village?"
description: "Neri needs a place to run a small service. LUMO discovers what a cloud is: resources shared through services and APIs, with a control plane and a data plane."
---

# 1. Why build a village?

*The empty plateau above the sea.*

<img src="assets/images/S01-open.webp" width="1536" height="1024" alt="LUMO, in a navy cape, listens with a hand on the chin while Neri, a bearded traveller with a bedroll, gestures at the empty grassy plateau above the sea, a white town on the far cliffs.">

The plateau is wide, windy and empty. Neri arrives with a small notebook and a simple wish: "I have a little service
to run. I don't want to buy a machine, wait for it, plug it in and look after it alone. I just want a place to run it."

LUMO looks at the empty ground and then at the sea, where ships come and go. One house for Neri would be easy. But
tomorrow someone else will come with another service, and the day after, ten more. Building a house by hand for each
of them would never end.

"What if the village had a town hall," LUMO says, "where anyone can ask for what they need, and the village builds
it for them, on ground it shares?" Neri frowns. "Then someone has to run the town hall." LUMO nods. "And someone has
to keep the fields where the work is done. Two different jobs."

<img src="assets/images/S01-v1.webp" width="1024" height="1024" loading="lazy" alt="LUMO and a villager in a work apron lean over a plan of a small stone house laid out on a table, with building blocks, a compass and a lit brass lantern.">

The small lantern gives its first, uncertain light.

<img src="assets/images/S01-v2.webp" width="1024" height="1024" loading="lazy" alt="On a wooden table above the sea lie three rough foundation stones, a folded blank parchment and a small brass lantern, with the white island town in the distance.">

> [!IMPORTANT]
> **Where the picture stops.** A cloud is not one village in one place. Its services and its resources can be spread
> over many machines and many networks, in one room or in several data centres. The town hall and the fields are two
> roles, not necessarily two buildings.

## What it is in OpenStack

**OpenStack** is software that turns a set of servers, networks and disks into a **cloud**: people ask for resources
(a virtual machine, a network, a disk) through **services**, each with an **API**, and get them in minutes, without
touching the hardware.

<img src="assets/images/S01-bridge-cloud.webp" width="1600" height="1000" loading="lazy" alt="On the left, LUMO and Neri crouch by the first paving stones of the plateau; on the right, a drawing shows three people with laptops sending requests to one service window, which drives a cloud of servers, a network and storage.">

Two words describe the two jobs LUMO saw:

- The **control plane** is the set of services that receive requests, check them, decide and keep records: the town
  hall. Keystone, Nova's API and scheduler, Neutron's server, Glance, Cinder's API, and the database and message queue
  they rely on.
- The **data plane** is where the resources actually run and the traffic actually flows: the fields. The hypervisors
  that run virtual machines, the network nodes and virtual switches that carry their traffic, the storage that holds
  their disks.

Both are functions. In a small lab one server can do both; in production they are usually separated so that a busy
or broken machine does not stop the town hall.

<img src="assets/images/S01-bridge-control-plane.webp" width="1600" height="1000" loading="lazy" alt="On the left, LUMO and a villager study a plan of the village; on the right, a drawing shows groups of people sending requests to a set of gears, which hand out wood, bricks and stone: the control plane deciding over shared resources.">

<img src="assets/images/S01-bridge-data-plane.webp" width="1600" height="1000" loading="lazy" alt="On the left, LUMO looks over a model of the village with a glowing path linking its houses; on the right, a drawing shows a cloud of gears sending instructions to a server, where a virtual machine runs and its traffic goes through network ports to the outside world.">

## From the village to OpenStack

```mermaid
flowchart LR
    U["Neri<br/>(a user)"] -->|"request through an API"| CP
    subgraph CP["Control plane (the town hall)"]
        API["Service APIs"]
        DB[("Databases")]
        MQ{{"Message queue"}}
    end
    CP -->|"instructions"| DP
    subgraph DP["Data plane (the fields)"]
        HV["Hypervisors<br/>run the VMs"]
        NET["Virtual network<br/>carries the traffic"]
        ST["Storage<br/>holds the disks"]
    end
```

A solid arrow is a request or an instruction in the direction shown. The two boxes are roles; one machine can belong
to both.

## See it for real

There is no single command that shows "the cloud". The operator's view is an architecture diagram that says which
machines play which role: controllers, compute nodes, network nodes, storage. The
[Deployment patterns](../deploy/) show several real ones.

**The lantern:** small and almost out. A first glow appears.

**Next:** LUMO decides to have the town hall built before welcoming the first inhabitant.
[2. The town hall takes shape →](02-the-town-hall-takes-shape.md)
