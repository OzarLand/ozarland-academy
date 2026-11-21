---
title: "9. Neri's first house"
description: "With an image, a flavor and a network, LUMO asks for Neri's first instance. Nova builds it on a chosen host; ACTIVE does not mean the service works."
remember:
- "An instance is created by Nova from an image (or a bootable volume), a flavor and one or more networks."
- "<code>ACTIVE</code> means Nova runs the VM; it does not prove that the guest system or the application works."
- "A disk created from the image on the host is deleted with the instance; a volume can outlive it."
scenarios:
- title: "Deleting an instance to save space"
  situation: "Neri's instance booted from its image. Neri wants to delete it to free capacity and assumes the data on its root disk \"will be kept somewhere\"."
  ask: "What would you do?"
  choices:
  - text: "Explain that a disk created from the image is deleted with the instance, and copy the data to a volume or an object store first."
    verdict: "best"
    why: "Only data on a volume (or copied elsewhere) survives the deletion of an instance that booted from an image."
  - text: "Take a snapshot of the instance, then delete it."
    verdict: "risky"
    why: "A snapshot keeps an image of the disk, which can work, but nobody checked that the snapshot is complete or restorable before deleting."
  - text: "Delete it: OpenStack keeps the root disk anyway."
    verdict: "avoid"
    why: "The local root disk is deleted with the instance."
  see: "what-it-is-in-openstack"
quiz:
- q: "<code>openstack server show</code> says <code>ACTIVE</code>. Is Neri's service up?"
  options:
  - "Yes, ACTIVE means the application answers"
  - "Not necessarily: check the console log and the service itself"
  answer: 1
  explain: "ACTIVE is Nova's view of the VM. The guest may still be booting, or the application may have failed."
  see: "what-it-is-in-openstack"
- q: "Which three things does <code>server create</code> need in the simplest case?"
  options:
  - "An image, a flavor and a network"
  - "A token, a quota and a router"
  - "A volume, a floating IP and a security group"
  answer: 0
  explain: "Image (what it starts with), flavor (how much it gets) and a network (where it is connected); the rest is optional."
  see: "see-it-for-real"
---

# 9. Neri's first house

*A compute workshop.*

<img src="assets/images/S09-open.webp" width="1536" height="1024" alt="Neri and LUMO watch a keeper kneel at the door of a small new stone house, joined to a path of stones and fine golden lines.">

Everything is ready: the tile from the library, the small profile, the connector on Neri's road. LUMO hands the three
to Rami at the workshop desk and signs the request with Maë's token. Rami checks the request, Sacha picks a workshop,
Noor writes down the tools it will use, and in the chosen workshop the foreman starts the build.

A few minutes later a small house stands in the workshop, connected to Neri's road. Rami's board turns from *building*
to *active*. Neri claps. LUMO keeps the lantern steady. "Active means the house is standing and powered. It doesn't
tell us yet that your service inside is running. Let's look."

<img src="assets/images/S09-v1.webp" width="1024" height="1024" loading="lazy" alt="LUMO and a keeper look at a small brass panel where a grey light has turned green.">

Neri opens the console of the house: the system inside is still starting. Two minutes later it is up.

<img src="assets/images/S09-v2.webp" width="1024" height="1024" loading="lazy" alt="LUMO stands before a glowing machine at the centre of four cards: a disk, a blank tile, a stack of layers and a network cable.">

> [!IMPORTANT]
> **Where the picture stops.** `ACTIVE` does not guarantee that the guest operating system or the application works:
> it only says what Nova did. And whether the disk survives the deletion of the instance depends on how it booted: a
> disk created from the image on the host is deleted with the instance; a volume can outlive it.

## What it is in OpenStack

An **instance** (or *server*) is a virtual machine created by **Nova** from:

- an **image** (what the disk starts with) or a bootable volume,
- a **flavor** (how much CPU, memory and disk),
- one or more **networks** or ports (where it is connected),
- optionally a key pair, security groups, user data, and more.

Nova authenticates the request, schedules it (scene 6), and asks `nova-compute` on the chosen host to create the
virtual machine with the hypervisor, after Neutron has bound its port and Glance has provided the image. The instance
goes through states such as `BUILD`, then `ACTIVE`, or `ERROR` if something failed.

## From the village to OpenStack

```mermaid
sequenceDiagram
    participant N as Neri
    participant NA as Nova API
    participant SC as Scheduler + Placement
    participant NC as nova-compute (chosen host)
    participant GL as Glance
    participant NE as Neutron
    N->>NA: server create (image, flavor, network) + token
    NA-->>N: accepted: status BUILD
    NA->>SC: choose a host (through the conductor)
    SC-->>NC: build here
    NC->>GL: fetch the image
    NC->>NE: bind the port on this host
    NC->>NC: start the VM with the hypervisor
    Note over N,NC: status ACTIVE means the VM runs, the guest may still be booting
```

## See it for real

```bash
openstack server create --image <IMAGE> --flavor <FLAVOR> --network <NET> <SERVER>
openstack server show <SERVER>
openstack console log show <SERVER>
```

`server show` gives the status and the fixed IP; the console log shows whether the guest has finished booting.

**The lantern:** steady on the first house. It does not promise that the house will always be available.

**Next:** the house is on Neri's private road. How does anyone from outside reach it?
[10. The bridge to the outside →](10-the-bridge-to-the-outside.md)
