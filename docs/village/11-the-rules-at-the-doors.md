---
title: "11. The rules at the doors"
description: "LUMO reads the rules applied at the doors of Neri's house and allows only what the service needs. Security groups filter traffic at each port."
remember:
- "A security group is a set of rules applied to ports; anything not allowed is dropped."
- "Rules are stateful: replies to an allowed connection go back without an extra rule."
- "Open only what the service needs, from the narrowest source possible."
scenarios:
- title: "Remote login for Neri"
  situation: "Neri needs SSH to the instance. A quick fix would be a rule allowing TCP 22 from 0.0.0.0/0."
  ask: "What would you do?"
  choices:
  - text: "Allow TCP 22 only from Neri's own address, and write down why."
    verdict: "best"
    why: "It gives Neri access without exposing SSH to the whole Internet."
  - text: "Allow TCP 22 from 0.0.0.0/0 for a day, then remove it."
    verdict: "risky"
    why: "Temporary rules are often forgotten, and exposed SSH is scanned within minutes."
  - text: "Allow all TCP ports from 0.0.0.0/0 so Neri never has to ask again."
    verdict: "avoid"
    why: "Every open port is a door someone else can use."
  see: "what-it-is-in-openstack"
quiz:
- q: "Incoming HTTPS is allowed by a rule. Do the replies need an egress rule?"
  options:
  - "Yes, every direction needs its rule"
  - "No, security groups are stateful"
  answer: 1
  explain: "Replies to an allowed connection are allowed automatically."
  see: "what-it-is-in-openstack"
- q: "Where are security group rules applied?"
  options:
  - "On each port"
  - "On the router only"
  - "On the physical switch"
  answer: 0
  explain: "They apply to the ports of the instances, wherever those run."
  see: "what-it-is-in-openstack"
---

# 11. The rules at the doors

*The board of network rules.*

<img src="assets/images/S11-open.webp" width="1536" height="1024" alt="Neri and LUMO examine a round brass frame with a network socket and an arrow passing through it, a rule card in Neri's hand.">

On a board next to Linh's workshop hang the rules of each door. By default Neri's house lets its own people go out
and lets nobody in. A visitor who crosses the bridge reaches the door and stops there.

LUMO reads Neri's needs again: the service answers on one port, and Neri wants to log in to look after it. So LUMO
adds exactly two rules: let in the web traffic of the service, and let in remote login, but only from Neri's own
address. Nothing else.

<img src="assets/images/S11-v1.webp" width="1024" height="1024" loading="lazy" alt="LUMO studies a map where a few lit roads cross the water while the others stay dark.">

"Why not open everything? It would be simpler," Neri asks. LUMO shields the flame from the wind. "Every open door is a
door someone else can use. We open what the service needs, and we write down why."

<img src="assets/images/S11-v2.webp" width="1024" height="1024" loading="lazy" alt="LUMO points at a board where a translucent panel lets one arrow through from a server to a house door and holds another back.">

> [!IMPORTANT]
> **Where the picture stops.** Security groups are not physical fences or guards. They are rules applied to each
> port by the virtual network. A rule that is too broad (for example SSH open to `0.0.0.0/0`) can expose a service to
> the whole Internet.

## What it is in OpenStack

- A **security group** is a named set of **rules** applied to the **ports** of instances. Each port can have several
  groups.
- Each rule allows traffic: a direction (ingress or egress), a protocol, a port range, and a remote source (an IP
  range or another security group). Anything not allowed is dropped.
- They are **stateful**: if an incoming connection is allowed, its replies go out without an extra rule, and the
  other way round.
- The `default` group of a project allows all outgoing traffic and incoming traffic only from members of the same
  group.

## From the village to OpenStack

```mermaid
flowchart LR
    V["Visitor on the Internet"] -->|"TCP 443"| SG
    A["Neri's address 198.51.100.7"] -->|"TCP 22"| SG
    X["Anyone else"] -->|"TCP 22"| SG
    subgraph SG["Security group of the port"]
        R1["allow ingress TCP 443 from 0.0.0.0/0"]
        R2["allow ingress TCP 22 from 198.51.100.7/32"]
    end
    SG -->|"allowed"| P["Port of Neri's instance"]
    SG -.->|"dropped: no rule"| D["✕"]
```

## See it for real

```bash
openstack security group list
openstack security group rule list <SG>
openstack security group rule create --protocol tcp --dst-port 443 --remote-ip 0.0.0.0/0 <SG>
```

**The lantern:** the beam narrows onto the openings that are actually needed.

**Next:** the network is under control. LUMO turns to where the data lives.
[12. The attached disk and the object archive →](12-the-attached-disk-and-the-archive.md)
