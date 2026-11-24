---
title: "14. Behind the town hall"
description: "Behind the offices, Pax carries messages between services and Talia keeps their records: the message queue and the databases of the control plane."
remember:
- "RabbitMQ carries messages between the parts of the services (RPC and notifications), not the traffic of the VMs."
- "Each service keeps its state in its own SQL database, usually MariaDB with Galera in production."
- "When the message queue or the databases are in trouble, the whole control plane is."
quiz:
- q: "Which component carries the messages from the Nova conductor to <code>nova-compute</code>?"
  options:
  - "RabbitMQ"
  - "MariaDB"
  - "Neutron"
  answer: 0
  explain: "RPC messages between service components go through the message queue."
  see: "what-it-is-in-openstack"
- q: "Do the disks of the virtual machines live in the MariaDB databases?"
  options:
  - "Yes"
  - "No, the databases hold the state of the services"
  answer: 1
  explain: "The databases describe instances, networks, volumes…; the disks live on the hosts or on the storage back end."
  see: "what-it-is-in-openstack"
---

# 14. Behind the town hall

*The service corridor.*

<img src="assets/images/S14-open.webp" width="1536" height="1024" alt="LUMO walks the service corridor behind the town hall, where keepers sort sealed capsules and closed registers.">

Behind the offices runs a narrow corridor that visitors never see. Pax hurries along it with sealed capsules:
messages from one office to another. "Build this house." "That house is ready." "This workshop is still alive." Pax
does not read them and never carries the visitors themselves. Pax carries the town hall's own mail.

At the end of the corridor Talia keeps the closed registers of every office: which houses exist, on which roads,
with which connectors, in whose file. "If these were lost, the houses would still stand," Talia says, "but the town
hall would no longer know they are there." The operators check on Pax and Talia every morning, before anything else.

<img src="assets/images/S14-v1.webp" width="1024" height="1024" loading="lazy" alt="Outside a small door of the town hall, LUMO watches two symbols, one for messages and one for stacked records, travel back and forth along curved arrows.">

<img src="assets/images/S14-v2.webp" width="1024" height="1024" loading="lazy" alt="LUMO leans over a map of the village where small capsules move along the paths between the town hall and the other buildings.">

> [!IMPORTANT]
> **Where the picture stops.** These components do not hold the disks of the virtual machines or their traffic. They
> hold the state and the internal messages of the control plane. Their exact role, and how they are made highly
> available, depend on the architecture that was deployed.

## What it is in OpenStack

- A **message queue**, usually **RabbitMQ**, carries remote procedure calls and notifications between the parts of a
  service, for example from the Nova conductor to `nova-compute`, or from the Neutron server to its agents.
- A **SQL database**, usually **MariaDB** with **Galera** clustering in production, stores the state of each service:
  instances, networks, ports, volumes, projects, and so on. Each service has its own database.
- **Memcached** often caches tokens and other short-lived data.

When RabbitMQ or the database is in trouble, the whole control plane is in trouble. Several of the
[VM runbooks](../runbooks/) start there.

## From the village to OpenStack

```mermaid
flowchart LR
    NAPI["Nova API"] -->|"writes / reads"| DB[("MariaDB / Galera<br/>service state")]
    NAPI -->|"RPC message"| MQ{{"RabbitMQ"}}
    MQ -->|"RPC message"| COND["Nova conductor"]
    COND -->|"writes / reads"| DB
    COND -->|"RPC message"| MQ
    MQ -->|"RPC message"| NC["nova-compute"]
    VM["VM traffic and disks"] -.-|"never through here"| MQ
```

## See it for real

These are operator views, on the controllers of a Kolla-Ansible deployment:

```bash
docker ps --filter name=rabbitmq --filter name=mariadb
docker exec rabbitmq rabbitmqctl cluster_status
docker exec -it mariadb mariadb -u root -p -e "SHOW STATUS LIKE 'wsrep_cluster_size';"
```

Use `podman` instead of `docker` if your deployment runs Podman. The last command asks for the database root password
of the deployment. On a Kolla-Ansible deployment it is `database_password` in `/etc/kolla/passwords.yml`; type it at
the prompt (`-it` lets `-p` ask for it) rather than after `-p`, so that it stays out of your shell history. In a
healthy three-controller cluster, `wsrep_cluster_size` is `3`.

The client is `mariadb`: the Academy [lab](../lab/exercises/10-lose-one-controller/) and
[runbooks](../runbooks/recovery/galera-cluster-lost-quorum-database-unavailable/) were written on 2026.1, whose MariaDB
image has no `mysql` command. The Academy does not say whether the images of older releases still have one.

**The lantern:** it lights the corridor without suggesting that one component explains everything.

**Next:** further down, specialised workshops add more to the village.
[15. The specialised workshops →](15-the-specialised-workshops.md)
