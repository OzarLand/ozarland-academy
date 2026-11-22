---
title: "Labs"
description: "The two Quick lab variants, single VM and multinode: what each lets you practise, the VMs and quota it needs, and how long a run takes."
---

# Labs

Two variants of the same lab, deployed with Kolla-Ansible on VMs of an OpenStack cloud. Pick one by what you want to
practise; each guide gives its requirements, quick start, costs and how to delete everything.

| | [Single VM](openstack-cloud/index.md) (`openstack-cloud`) | [Multinode](openstack-cloud-multinode/index.md) (`openstack-cloud-multinode`) |
|---|---|---|
| 🎯 **What you can practise** | The core services: DHCP, metadata, Nova, Open vSwitch, security groups and floating IPs (exercises 1 to 6) | 3 VMs: live migration, a failed compute, host maintenance (exercises 7 to 9). 5 VMs: also a failed controller, Galera and RabbitMQ, VIP failover (exercises 10 and 11) |
| 🖥️ **VMs and quota** | 1 VM: 4 vCPU, 16 GB RAM, 50 GB disk | 3 VMs: 12 vCPU, 32 GB RAM. 5 VMs (`CONTROLLERS="3"`): 20 vCPU, 64 GB RAM |
| ⏱️ **Time** | About 1 hour (57 min measured, `create.sh` to `destroy.sh`) | Measured, `create.sh` to `destroy.sh`: 65 min with 3 VMs, about 75 min with 5 VMs |

🌱 **New to OpenStack? Start with the single VM.** The cost of a run and of a forgotten day is in
[Pick your lab](../index.md#pick-your-lab) on the home page and in each guide. Once a lab is up, break and repair it with
the [exercises](../exercises/index.md).
