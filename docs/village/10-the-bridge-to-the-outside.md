---
title: "10. The bridge to the outside"
description: "LUMO links Neri's network to the outside through a router and gives the house a floating IP: a public address mapped to its private one."
remember:
- "A Neutron <strong>router</strong> connects subnets and, through its external gateway, an external network."
- "A <strong>floating IP</strong> comes from the external network and is associated with a port; the router translates it to the fixed IP."
- "A floating IP alone does not give access: routes and security group rules must allow the traffic."
scenarios:
- title: "The floating IP does not answer"
  situation: "Neri associated a floating IP with the instance, but nothing answers on port 443 from outside."
  ask: "What would you do?"
  choices:
  - text: "Check that the router has an external gateway and that a security group rule allows TCP 443 in."
    verdict: "best"
    why: "Association alone is not enough: the router must reach the external network and the security group must allow the traffic."
  - text: "Allocate a second floating IP and try again."
    verdict: "risky"
    why: "It changes nothing if the gateway or the rules are the problem, and it consumes a public address."
  - text: "Open all ports to 0.0.0.0/0 to rule out the security group."
    verdict: "avoid"
    why: "It exposes every service of the instance to the Internet; open only what the service needs."
  see: "what-it-is-in-openstack"
quiz:
- q: "Inside the instance, which address does the operating system see on its interface?"
  options:
  - "The floating IP"
  - "The fixed IP of its port"
  answer: 1
  explain: "The router translates between the floating IP and the fixed IP; the guest only knows its fixed IP."
  see: "what-it-is-in-openstack"
- q: "Where does a floating IP come from?"
  options:
  - "From the external network"
  - "From the project's private subnet"
  - "From Keystone"
  answer: 0
  explain: "Floating IPs are allocated from an external network and associated with a port."
  see: "what-it-is-in-openstack"
---

# 10. The bridge to the outside

*The gateway on the sea side.*

<img src="assets/images/S10-open.webp" width="1536" height="1024" alt="LUMO leans over a map of the village where a small round bridge links a blue marker on the private side to a red marker on the public quay.">

Neri's house stands on a private road that no ship can see. Down by the sea, Linh shows LUMO a small bridge: a router.
One side joins Neri's road, the other the big public quay where visitors arrive.

"A visitor can't use the private house number," Linh explains. "On the quay we hand out public numbers. You take one,
and you tie it to the connector of the house." LUMO ties a public number to Neri's house. From the quay, the house now
has an address; on the private road it keeps its own.

<img src="assets/images/S10-v1.webp" width="1024" height="1024" loading="lazy" alt="LUMO crouches between two stone posts linked by a golden arc, like a bridge from one side to the other.">

Neri asks if visitors can come in now. LUMO looks at the doors of the house. "There's a way in. Whether the doors
let them through is another matter."

<img src="assets/images/S10-v2.webp" width="1024" height="1024" loading="lazy" alt="LUMO points at a map where a glowing bridge joins two islands of houses.">

> [!IMPORTANT]
> **Where the picture stops.** The floating IP is different from the fixed internal IP: the instance itself only
> knows its fixed IP, and the router translates between the two. Associating a floating IP does not by itself give
> access: routes and security group rules must also allow the traffic.

## What it is in OpenStack

- A **router** (a Neutron object) connects subnets to each other and, through its **external gateway**, to an
  **external network** (a provider network that reaches the outside world).
- A **floating IP** is an address taken from the external network and associated with a **port** of an instance. The
  router performs the address translation (NAT) between the floating IP and the port's fixed IP.
- Outgoing traffic from instances without a floating IP usually leaves through the router with the router's own
  external address (source NAT).

## From the village to OpenStack

```mermaid
flowchart LR
    EXT["External network<br/>(public)"] --- R["Router<br/>external gateway"]
    R --- SUB["neri-subnet<br/>192.168.10.0/24"]
    SUB --- P["Port of the instance<br/>fixed IP 192.168.10.5"]
    FIP["Floating IP 203.0.113.20<br/>(from the external network)"] -.->|"associated with"| P
    VIS["Visitor"] -->|"203.0.113.20"| R
    R -->|"NAT to 192.168.10.5"| P
```

## See it for real

```bash
openstack router create <ROUTER>
openstack router set --external-gateway <PUBLIC_NET> <ROUTER>
openstack router add subnet <ROUTER> <SUBNET>
openstack floating ip create <PUBLIC_NET>
openstack server add floating ip <SERVER> <IP>
```

**On a real host.** With ML2/OVS and the L3 agent, a Neutron router is a `qrouter-<router-id>` network namespace on a
network host (with HA routers, on several, and only the `active` one carries the floating IP). The address
translation is done there by the host's own iptables: the floating IP sits on the router's `qg-` interface, and a
destination NAT (DNAT) rule in the namespace sends it to the instance's fixed IP. You can look, read-only, as root on
that host: `ip netns exec qrouter-<router-id> ip -brief addr` and `ip netns exec qrouter-<router-id> iptables -t nat -S`.
With ML2/OVN there is no namespace: the router is a logical router in the OVN database. To go further:
[Instance unreachable from outside](../runbooks/networking/instance-unreachable-from-outside/), section "Where the
router lives".

**The lantern:** the beam points at two different addresses and at the bridge between them.

**Next:** the bridge exists. LUMO checks which crossings are allowed.
[11. The rules at the doors →](11-the-rules-at-the-doors.md)
