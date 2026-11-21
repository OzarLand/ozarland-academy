---
title: "2. The town hall takes shape"
description: "A crew sets up the services of the town hall on the hosts. LUMO learns how Kolla-Ansible deploys and configures OpenStack services in containers."
remember:
- "Kolla-Ansible deploys the OpenStack services as containers on the hosts listed in an inventory, with the settings of <code>globals.yml</code>."
- "<code>bootstrap-servers</code> prepares the hosts, <code>prechecks</code> verifies them, <code>deploy</code> starts the services."
- "Kolla-Ansible builds the cloud; it does not create the users' machines. Users ask the deployed services."
quiz:
- q: "Neri wants a new virtual machine. Who handles that request?"
  options:
  - "Kolla-Ansible"
  - "The deployed OpenStack services (Nova, Neutron, Glance…)"
  answer: 1
  explain: "Kolla-Ansible deploys and changes the platform; once the services run, users talk to them through their APIs."
  see: "what-it-is-in-openstack"
- q: "Which command checks the hosts before anything is deployed?"
  options:
  - "<code>kolla-ansible prechecks</code>"
  - "<code>kolla-ansible deploy</code>"
  - "<code>openstack server create</code>"
  answer: 0
  explain: "<code>prechecks</code> verifies the hosts and the configuration; <code>deploy</code> then starts the services."
  see: "see-it-for-real"
---

# 2. The town hall takes shape

*The central deployment yard.*

<img src="assets/images/S02-open.webp" width="1536" height="1024" alt="In the paved yard of the town hall, a crew slides identical white crates onto racks inside a stone archway while LUMO, Neri and a crew member with a clipboard watch.">

The next morning a crew arrives with crates: all the same size, all labelled the same way, all packed the same way.
Jo, the crew leader, opens one. Inside is everything one service of the town hall needs to work, ready to be set down
on a host.

"We don't build each office by hand," Jo says. "We write down once which service goes on which host and how it is
configured. Then the crew follows the list, the same way every time." LUMO watches the crates go into the hall, one
service after the other: the register, the workshop desk, the network office, the library.

<img src="assets/images/S02-v1.webp" width="1024" height="1024" loading="lazy" alt="LUMO checks a list on a clipboard while a crew member in glasses slides an identical wooden crate onto a shelf.">

Before the first crate is opened, Jo checks the ground: are the hosts reachable, is there enough room, are the
addresses right? Only then does the crew unpack. When it is done, LUMO walks through the empty offices with the
lantern. Nobody lives in the village yet, but every desk is ready.

<img src="assets/images/S02-v2.webp" width="1024" height="1024" loading="lazy" alt="LUMO stands on a stone path between the town hall, whose offices are lined with installed crates, and terraces of equipment cabinets in the fields by the sea.">

> [!IMPORTANT]
> **Where the picture stops.** Kolla-Ansible deploys the services of the cloud. It does not create Neri's machine:
> once the services are running, users ask the services themselves, and Kolla-Ansible is out of the picture until
> the operators change or upgrade the platform.

## What it is in OpenStack

Each OpenStack service is a set of programs (an API, workers, agents) that must be installed, configured and kept
running on the right hosts. **Kolla** packages each of them as a **container image**: the crates. **Kolla-Ansible**
uses Ansible to put those containers on the hosts listed in an **inventory**, with the settings of `globals.yml`.

- The inventory says which host plays which role (controller, compute, network, storage).
- `bootstrap-servers` prepares the hosts, `prechecks` verifies them, `deploy` starts the services.
- The same files describe the platform every time, so it can be rebuilt, changed or upgraded the same way.

Kolla-Ansible is one deployment tool among several. The [OKD OpenStack lab](../okd/) shows another one, where
Kubernetes operators do this job.

<img src="assets/images/S02-bridge-kolla-ansible.webp" width="1600" height="1000" loading="lazy" alt="On the left, LUMO watches a crane lower a service crate in front of the town hall; on the right, a drawing shows configuration files driving a deployment tool, which places service containers on two hosts, before a user calls the deployed services.">

## From the village to OpenStack

```mermaid
flowchart LR
    OP["Operator"] -->|"runs"| KA["Kolla-Ansible<br/>+ inventory + globals.yml"]
    KA -->|"deploys containers"| C1["Controller hosts<br/>Keystone, Nova API,<br/>Neutron server, Glance…"]
    KA -->|"deploys containers"| C2["Compute hosts<br/>nova-compute, libvirt,<br/>network agents"]
    U["Neri"] -.->|"later, asks the services,<br/>not Kolla-Ansible"| C1
```

A dotted arrow is a later, separate interaction: users talk to the deployed services.

## See it for real

On the deployment host, with an inventory called `multinode` (operator work, not something a user runs):

```bash
kolla-ansible bootstrap-servers -i ./multinode
kolla-ansible prechecks -i ./multinode
kolla-ansible deploy -i ./multinode
```

You will run these yourself in the [Quick lab](../lab/), and the [day-2 module](../day2/) explains what each of them
really does.

**The lantern:** the flame steadies and lights the threshold of the town hall.

**Next:** the offices are ready. Now, who is allowed to use them?
[3. The register and the passes →](03-the-register-and-the-passes.md)
