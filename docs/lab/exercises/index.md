---
title: "Exercises"
description: "Eleven exercises that break one thing on purpose in the lab and repair it with a runbook, and what to do before each."
---

# Exercises

Six short exercises on the all-in-one lab, three on the multinode variant and two on its 3-controller size. Each
one breaks one thing on purpose, shows you what an operator would see, and walks you through the repair with a
runbook from [openstack-vm-runbooks](../../runbooks/) (exercises 10 and 11 use
pages of [kolla-ansible-deployment-patterns](../../deploy/)
instead). The runbooks of exercises 1 to 9 are
`status: lab-verified`; exercise 10 relies on a `draft` pattern page. The exercises themselves were run on the
reference cloud by OzarLand's lab agents (1 to 6 on 2026-10-23, 7 to 11 on 2026-10-25); 10 and 11 were edited
after that run.

<img src="../assets/images/S1-network.webp" width="1536" height="1024" loading="lazy" alt="LUMO and a colleague with a spyglass look along the harbour paths and footbridges while a light mist drifts over the sea and a worker checks a brass railing.">

| # | Exercise | Time | What you learn |
|---|---|---|---|
| 1 | [DHCP agents down](01-dhcp-agents-down.md) | 20 min | An instance can be `ACTIVE` and still have no address |
| 2 | [Metadata agents down](02-metadata-agents-down.md) | 20 min | Where an instance gets its SSH key, and what happens without it |
| 3 | [nova-compute down](03-nova-compute-down.md) | 15 min | The control plane and the instances are separate: one can fail without the other |
| 4 | [Restarting nova_libvirt](04-restart-nova-libvirt.md) | 10 min | A restart that looks risky, and why it is not |
| 5 | [Restarting the Open vSwitch agent](05-restart-ovs-agent.md) | 10 min | The agent programs the network; it does not carry the traffic |
| 6 | [Instance unreachable from outside](06-instance-unreachable-from-outside.md) | 20 min | Security groups and floating IPs, checked in order |

### Multinode variant

<img src="../assets/images/S1-failure-and-maintenance.webp" width="1536" height="1024" loading="lazy" alt="On a stone quay, one server rack stands behind a rope while workers fit a second rack inside a wooden scaffold, watched by LUMO and a traveller with a backpack.">

These three need two computes: run them on the
[multinode variant](../variants/openstack-cloud-multinode/index.md), not on the all-in-one lab. They were
[run on a lab](https://github.com/OzarLand/openstack-quick-lab/pull/10#issuecomment-6397487220) on 2026-10-25 (multinode variant, 1 controller + 2 computes). The runbook of exercises 8 and 9 is now
`status: lab-verified`.

| # | Exercise | Time | What you learn |
|---|---|---|---|
| 7 | [A compute goes down: fence it before you evacuate](07-compute-down-fence-before-evacuate.md) | 30 min | Why a compute must be off for sure before its instances are rebuilt elsewhere |
| 8 | [Drain a compute for planned maintenance](08-drain-a-compute-for-maintenance.md) | 30 min | Disable, move the instances away, work, enable: maintenance without downtime |
| 9 | [Live migration between the two computes](09-live-migration-between-computes.md) | 20 min | What moving a running instance costs its users, measured with a ping |

### Multinode variant, 3 controllers

<img src="../assets/images/S1-controllers-and-quorum.webp" width="1536" height="1024" loading="lazy" alt="At dusk, LUMO and three companions look from a terrace at three towers joined by an arched bridge across the water; only the nearest tower has its lantern lit.">

These two need the 5-VM size of the multinode variant (`CONTROLLERS="3"`). They were
[run on a lab](https://github.com/OzarLand/openstack-quick-lab/pull/15#issuecomment-6399273095) on 2026-10-25
(multinode variant, 3 controllers + 2 computes).

| # | Exercise | Time | What you learn |
|---|---|---|---|
| 10 | [Lose one controller: what keeps working](10-lose-one-controller.md) | 40 min | The VIP moves, two of three is still a quorum, a hung controller costs more than a dead one, a controller rejoins |
| 11 | [Lose two controllers: quorum lost, and recovered](11-lose-two-controllers-quorum.md) | 30 to 45 min | Why a minority stops serving, when Galera recovers by itself, and how `mariadb-recovery` rebuilds the cluster when it does not |

> **Why the exercises use `systemctl`, not `docker`, to stop a service**
>
> Kolla-Ansible gives each container a systemd unit, `/etc/systemd/system/kolla-<container>-container.service`
> ([release note](https://github.com/openstack/kolla-ansible/blob/stable/2026.1/releasenotes/notes/add-systemd-container-control-b85dff9ec5fae313.yaml);
> [the code that writes the unit](https://github.com/openstack/kolla-ansible/blob/stable/2026.1/ansible/module_utils/kolla_systemd_worker.py)). It is still the case in
> 2026.1, the release of these labs.
>
> - The unit starts the container with `docker start -a <container>` and stops it with `docker stop`.
> - With Kolla-Ansible's default `docker_restart_policy: "unless-stopped"`
>   ([`ansible/group_vars/all/common.yml`](https://github.com/openstack/kolla-ansible/blob/stable/2026.1/ansible/group_vars/all/common.yml)), the unit gets `Restart=always`.
> - So `docker stop <container>` alone is undone: systemd starts the container again. `systemctl stop
>   kolla-<container>-container.service` keeps it stopped.
> - The delay before systemd restarts it (`RestartSec`) comes from `docker_client_timeout`: one tenth of it, minus one
>   second. It is 11 s with Kolla-Ansible's default of 120 s; these labs set 600 s, so **59 s**. On the 5-VM lab, a
>   `neutron_dhcp_agent` stopped with `docker stop` was running again about 70 s later
>   ([measurement](https://github.com/OzarLand/openstack-quick-lab/pull/13#issuecomment-6398277862)).
>
> The exercises use `docker` only to look (`docker ps`, `docker exec`, `docker logs`). On a deployment without these
> units (an older release, or another deployment tool), use that tool's own way to stop a service.

## Runbooks and patterns in the exercises

The runbooks and the deployment pages that the exercises name belong to later stops of the
[Academy](../../): runbooks are stop 4, deployment patterns stop 2. You do not need to have read those stops, and you
should not read the runbook first. In each exercise you break the lab, look at what you see, and only then open the
runbook for the repair step ("Diagnose and repair with the runbook", or "Read the runbook" in exercise 4). The page tells you
where to start in it, for example at its **Quick checks**.

- **Exercises 1 to 9.** The runbook is the repair step of the exercise: open it at that step. What you learn is
  the method of the runbook, so the rest of the runbook can wait. To go further, read it in full later, in
  [stop 4](../../runbooks/).
- **Exercise 10.** The pattern is background: it explains how the virtual IP, keepalived and the clusters are set up in
  this lab. To go further, read it in [stop 2](../../deploy/).
- **Exercise 11.** Steps 1 to 3 and the check need no other page. The recovery of step 4 (optional) follows a procedure of
  stop 2, which the exercise names with its warning.

## Before every exercise

- The lab is running, and you followed its variant's guide to the end.
- You are logged in to the lab VM over SSH, with `sudo`.
- The OpenStack client is loaded, with the admin credentials:

  ```bash
  source ~/kolla-venv/bin/activate
  . /etc/kolla/admin-openrc.sh
  ```

The lab's scripts run Kolla-Ansible's `init-runonce`, which creates the resources the exercises use (the
[variant's guide](../variants/openstack-cloud/index.md#inside-the-lab) lists them too):

| Resource | Name |
|---|---|
| Test image | `cirros` |
| Flavor | `m1.tiny` |
| Tenant network, behind the router `demo-router` | `demo-net` |
| External network | `public1` |
| Key pair | `mykey` |
| External network's address range | the `LAB_EXT_CIDR` setting of `config.env`, `10.99.0.0/24` by default |

The exercises write the external range as `10.99.0.0/24`. If you changed `LAB_EXT_CIDR` in `config.env` before
launching the lab, use your range instead.

On the all-in-one lab, the controller, the network node and the compute are the same VM: every command runs there.

Two things you will meet in every exercise:

- **Run the runbooks' `docker` and `systemctl` commands with `sudo`.** The runbooks write them without it (for
  example `docker ps -a …` and `systemctl start kolla-…`). Without `sudo`, the `ubuntu` user of the lab gets
  `permission denied while trying to connect to the docker API` and an authentication prompt.
- **`systemctl` prints a warning** such as `The unit file, source configuration file or drop-ins of
  kolla-…-container.service changed on disk. Run 'systemctl daemon-reload' to reload units.` It is harmless on
  these labs, and the command still worked: you do not need to run `daemon-reload`.

Wherever a page writes `<floating-ip>`, use the address printed by the `openstack floating ip create` command just
before it. Note it down: you will also need it in a second SSH session.

These exercises break things on purpose. Run them only on this disposable lab, never on a platform someone relies
on.

## When you are done

Delete the lab: [delete everything when you are done](../index.md#delete-everything-when-you-are-done).
