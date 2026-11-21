---
title: "4. Neri's file"
description: "LUMO opens a file for Neri at the town hall. A project is the scope that owns resources; a quota is a limit on what the project may use, not a reservation."
remember:
- "A <strong>project</strong> owns resources and is the scope in which users get roles."
- "A <strong>quota</strong> is a ceiling on what a project may use, per resource type."
- "A quota is not a reservation: a project can have room in its quota while the cloud itself is full."
scenarios:
- title: "Planning capacity from the quotas"
  situation: "Each of 20 projects has a quota of 100 vCPUs. A colleague concludes that the cloud is sized for 2,000 vCPUs \"because that is what the quotas allow\"."
  ask: "What would you do?"
  choices:
  - text: "Compare the quotas with the real capacity of the hypervisors and with actual usage, and say that quotas are ceilings, not reservations."
    verdict: "best"
    why: "Quotas limit each project; they do not reserve capacity. The sum of quotas often exceeds what the hosts can run, on purpose."
  - text: "Lower every quota so that their sum matches the capacity."
    verdict: "risky"
    why: "It can make sense on some clouds, but it wastes capacity when projects do not all use their full quota; it is a policy choice, not a fix."
  - text: "Accept the conclusion: the quotas describe the size of the cloud."
    verdict: "avoid"
    why: "A quota is not a reservation and says nothing about how many vCPUs the hosts really provide."
  see: "what-it-is-in-openstack"
quiz:
- q: "Neri's project has a quota of 10 instances and uses 2. Is a 3rd instance guaranteed?"
  options:
  - "Yes, the quota reserves room for it"
  - "No: the quota allows it, but the cloud must also have free capacity"
  answer: 1
  explain: "The quota only says what the project may ask for. Whether a request succeeds also depends on the free capacity of the cloud."
  see: "what-it-is-in-openstack"
---

# 4. Neri's file

*The administration office.*

<img src="assets/images/S04-open.webp" width="1536" height="1024" alt="Neri and LUMO sit at a desk of the administration office and open a new file with a leather notebook, a compass and a quill beside them.">

To let Neri ask for anything, LUMO opens a file in Neri's name at the administration office. Everything Neri asks for
will be recorded in that file: the machines, the networks, the disks. Neri may invite friends to work in the same
file later.

On the first page of the file LUMO writes limits: so many machines, so many processors, so much memory, so much disk.
"Is that what I get?" asks Neri. LUMO shakes the lantern gently. "No. That is the most you may ask for. Whether it is
there when you ask depends on what the village has left."

<img src="assets/images/S04-v1.webp" width="1024" height="1024" loading="lazy" alt="On a desk lie a closed folder tied with a cord and a leather-bound register, with a compass, a lantern and Neri's rolled bedroll.">

Neri looks out of the window at the fields. "So there is no fence around a corner of land with my name on it?"
"No fence," LUMO says. "Just a file, and a limit."

<img src="assets/images/S04-v2.webp" width="1024" height="1024" loading="lazy" alt="From a balcony, Neri and LUMO look over the village, where small coloured pennants mark the files of different people without any fences between them.">

> [!IMPORTANT]
> **Where the picture stops.** A project does not reserve a physical plot or a guaranteed share of the capacity. A
> quota is a ceiling on what the project may use, not a reservation: two projects can each have room left in their
> quota while the cloud itself is full.

## What it is in OpenStack

- A **project** (once called a *tenant*) is the unit of ownership and access. Resources belong to a project; users get
  roles on a project. It lives in a **domain**, which groups projects and users.
- A **quota** is a limit per project and per resource type: instances, vCPUs, RAM, volumes, gigabytes, floating IPs,
  networks, ports… Each service enforces its own quotas.
- Neither of them says anything about *where* the resources run. The scheduler decides that, later, for each request.

## From the village to OpenStack

```mermaid
flowchart TB
    D["Domain"] --> P["Project: neri-project"]
    U["User: neri"] -.->|"role: member"| P
    P --> R1["Instances"]
    P --> R2["Networks, ports"]
    P --> R3["Volumes"]
    Q["Quota of the project<br/>(ceilings, not reservations)"] -.->|"limits"| P
```

A dotted line is an association or a setting; a solid line is ownership.

## See it for real

```bash
openstack project show <PROJECT>
openstack quota show <PROJECT>
```

`quota show` gives the limits; whether there is room for a request depends on the cloud's free capacity too.

**The lantern:** the light falls on a file with clear edges, without drawing a fence around any field.

**Next:** LUMO can now look at the shared ground where the work is done.
[5. The shared fields →](05-the-shared-fields.md)
