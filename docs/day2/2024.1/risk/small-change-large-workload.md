---
title: Why a small change creates a large workload
description: Seven small changes that become a large workload in Kolla-Ansible 2024.1, each with the reason and the source.
tags: [risk, scaling, loop-notify, nova, neutron, rabbitmq, images, reconfigure, systemd]
remember:
  - "One option for nova-compute in <code>nova/nova-compute.conf</code> is not small: it targets every compute, and loop-notify adds the libvirt and ssh restarts. New in 2024.1: <code>nova/&lt;host&gt;/nova-compute.conf</code> reaches that compute only. <span class=\"ev ev-code\">CODE</span>"
  - "A rebuilt image of one service, once pulled, restarts its sibling containers on the same host too."
  - "One extra controller changes the transport URL in every messaging service everywhere."
  - "One container-engine option such as <code>docker_graceful_timeout</code> changes the systemd unit of every container, and the next check of each container reports it as changed. <span class=\"ev ev-code\">CODE</span>"
  - "Every run pays the per-host work: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute, independently of restarts. <span class=\"ev ev-code\">CODE</span>"
scenarios:
  - title: "A one-line nova-compute change"
    situation: "Your cloud has 40 computes. A ticket asks you to change one option for nova-compute on all of them. Your colleague says: \"It's a one-line change in <code>nova/nova-compute.conf</code>, just run a full <code>reconfigure</code> now and close the ticket.\""
    ask: "What would you do?"
    choices:
      - text: "Write the config first with <code>genconfig</code>, then apply it with <code>deploy-containers --limit</code>, batch by batch."
        verdict: "best"
        why: "One option for nova-compute targets every compute, and loop-notify adds the libvirt and ssh restarts <span class=\"ev ev-code\">CODE</span>. The page points to the pattern \"Write config first, apply in controlled batches\": <code>genconfig</code>, then <code>deploy-containers --limit</code> batch by batch."
      - text: "Run a full <code>reconfigure</code> of the cloud right away, as suggested."
        verdict: "avoid"
        why: "The change is not small: one option for nova-compute targets every compute, and loop-notify adds the libvirt and ssh restarts. On top of that, every run pays the per-host work <span class=\"ev ev-code\">CODE</span>: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute."
      - text: "Run <code>reconfigure</code> on all computes in one go, but only at night."
        verdict: "risky"
        why: "The time of day does not change the size of the change: it still targets every compute, and loop-notify still adds the libvirt and ssh restarts on each of them. The page's pattern applies the config in controlled batches with <code>deploy-containers --limit</code>."
  - title: "Raise the stop timeout"
    situation: "A colleague wants heat-engine to get more time to stop cleanly, and proposes to raise <code>docker_graceful_timeout</code> from 60 to 300 in <code>globals.yml</code> and run <code>reconfigure -t heat</code>, \"since only Heat is concerned\"."
    ask: "What would you know before you agree?"
    choices:
      - text: "That the value is part of the systemd unit of every container, so the next check of each container the run reaches reports a change and restarts it; plan it as a fleet-wide restart, in batches."
        verdict: "best"
        why: "<code>docker_graceful_timeout</code> goes into <code>docker_common_options</code>, which every container task passes, and into the unit text; <code>compare_container</code> compares the whole unit file <span class=\"ev ev-code\">CODE</span>. <code>-t heat</code> reaches only the Heat containers, but every later run that checks another container restarts it."
      - text: "Nothing: a stop timeout only matters when a container stops, so the change restarts nothing."
        verdict: "avoid"
        why: "The unit text changes, and <code>compare_container</code> reports a container as changed when its unit file differs from the rendered one <span class=\"ev ev-code\">CODE</span>; the restart handler then restarts it."
      - text: "That only Heat will ever see the new value, because the run is tagged <code>heat</code>."
        verdict: "risky"
        why: "The tag limits which containers this run checks, not which containers the global value reaches: the next untagged or other-tag run checks the other containers against the new unit text and restarts them <span class=\"ev ev-code\">CODE</span>."
quiz:
  - q: "You change one option for nova-compute in <code>/etc/kolla/config/nova/nova-compute.conf</code>. Why is it a large change?"
    options: ["It is not: only one container restarts", "It targets every compute, and loop-notify adds the libvirt and ssh restarts"]
    answer: 1
    explain: "First row of the table."
  - q: "The image of one service is rebuilt and pulled. What else restarts?"
    options: ["Nothing else", "Its sibling containers on the same host"]
    answer: 1
    explain: "Row \"Rebuilt image of one service\": the role's check loop notifies the handlers of every container of that role on the host."
  - q: "You change <code>docker_graceful_timeout</code>. Which containers can a later run restart?"
    options: ["None: the timeout is read only when a container stops", "Every long-running container it checks, because their systemd unit text changed"]
    answer: 1
    explain: "Row \"One container-engine option\" <span class=\"ev ev-code\">CODE</span>."
  - q: "Does a run with no change cost anything per compute?"
    options: ["No, nothing happens", "Yes: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute"]
    answer: 1
    explain: "Every run pays the per-host work <span class=\"ev ev-code\">CODE</span>, independently of restarts."
---

# Why a small change creates a large workload

Why a small change can create a large workload in Kolla-Ansible 2024.1: seven small changes, each with why it is large
and the source lines and sections that show it. The six rows of 2023.1 still hold, two with changes; the row on
container-engine options is new on this page. The per-host work that every run pays, independently of restarts, closes
the page.

<img src="../assets/images/S3-small-change-large-effect.webp" width="1536" height="1024" loading="lazy" alt="Jo, holding a crate, and LUMO, reading, stand by a large brass gear mechanism on a bench where a small brass key lies on a parchment.">

| Small change | Why it is large | Source |
|---|---|---|
| One option for nova-compute | `/etc/kolla/config/nova/nova-compute.conf` targets every compute; loop-notify adds libvirt + ssh restarts (with the default Nova settings, which enable the `nova_libvirt` and `nova_ssh` containers). **New in 2024.1:** the same option in `/etc/kolla/config/nova/<host>/nova-compute.conf` is merged into that host's `nova-compute/nova.conf` only, so it reaches one compute | `nova.yml:125-147`; `roles/nova-cell/tasks/config.yml:69-89` (sources at `:78`, `:80`); `roles/nova-cell/tasks/check-containers.yml:2-22`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| `enable_<new service>: yes` | changes fluentd/logrotate on every host (at the next run of the `common` play: no tag or `-t common`) and `nova.conf` sections on every compute (e.g. `[barbican]`) | `roles/common/defaults/main.yml:154-158`, `roles/common/tasks/config.yml:205-215`; `site.yml:88-103`; `roles/nova-cell/templates/nova.conf.j2:259-264`; [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| One extra controller | changes the transport URL in every messaging service everywhere | `group_vars/all.yml:248`; [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |
| A server-side ML2 option | still does not reach the agents: `ml2_conf.ini` (and its overrides) is rendered for `neutron-server` and `neutron-infoblox-ipam-agent` only, and `openvswitch_agent.ini` and `linuxbridge_agent.ini` do not merge the `ml2_conf.ini` overrides. A file added under `neutron/plugins/` in the custom config is still copied to every Open vSwitch and Linux bridge agent and restarts them | `roles/neutron/tasks/config.yml:159-179`, `:181-213`, `:15-21`, `:485-506`; [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code) |
| Rebuilt image of one service | once the new image is on the host (a same-tag rebuild needs an explicit `pull`), its siblings on the same host restart too: the image ID differs for one item of the role's check loop, and that loop notifies the handlers of every item | `module_utils/kolla_docker_worker.py:107-122` (Podman: `module_utils/kolla_podman_worker.py:317-335`); `roles/nova-cell/tasks/check-containers.yml:2-22`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [F4](../reference/findings.md#f4) |
| Any OpenStack API service `-t <svc>` | runs the service's include in the `loadbalancer` play (haproxy configuration; new in 2024.1: also the service's block of `external-frontend-map` when `haproxy_single_external_frontend` is set, default `false`) and Keystone registration even with no change. Still holds in 2024.1: it does not run common, since no role has a `meta` directory and the common play is tagged `common` only; the DB sync runs on every `deploy` and, for most services, on every reconfigure. Neutron too: its bootstrap (`neutron-db-manage ... upgrade head`) has no `kolla_action` condition and runs on every `deploy` and `reconfigure`. Infrastructure tags such as `-t haproxy` run the `loadbalancer` play, whose 39 service includes are all evaluated and run for the enabled services, but no Keystone registration or DB sync | [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), [Reconfigure a single service §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects); `site.yml:88-103`, `:105-326`; `roles/haproxy-config/tasks/main.yml:25-53`, `group_vars/all.yml:931`; `roles/neutron/tasks/reconfigure.yml:2`, `roles/neutron/tasks/deploy.yml:20`, `roles/neutron/tasks/bootstrap_service.yml:2-21`; kolla `docker/neutron/neutron-server/extend_start.sh:5-13` |
| One container-engine option (`docker_graceful_timeout`, `docker_client_timeout`, `docker_restart_policy`, `docker_restart_policy_retry`; new on this page) | the value goes into `docker_common_options`, which every container task passes, and into the systemd unit text of every container. `compare_container` compares the whole unit file with the rendered one, so the next check of every long-running container reports it as changed and its restart handler restarts it, rewriting the unit; loop-notify then restarts the rest of its role on that host. One-shot containers have no unit; Swift `deploy` has no check task. A `docker_restart_policy` change between `unless-stopped` and `always` renders the same `Restart=always` and changes nothing | `group_vars/all.yml:139`, `:142-153`; `library/kolla_container.py:361-393`; `module_utils/kolla_systemd_worker.py:20-39`, `:56-79`, `:154-167`, `:172-185`; `module_utils/kolla_container_worker.py:32`, `:58-65`; `module_utils/kolla_docker_worker.py:439-459`; [F16](../reference/findings.md#f16) |

> [!NOTE]
> The first 2024.1 `deploy` or `reconfigure` after an upgrade from 2023.1 is a large workload with no operator change
> at all [CODE]: the 2024.1 unit template differs from the one 2023.1 wrote, so every container whose unit 2023.1 wrote
> is reported as changed at its first 2024.1 check ([F16](../reference/findings.md#f16);
> `module_utils/kolla_systemd_worker.py:20-39`, `:154-167`); and `om_enable_rabbitmq_quorum_queues` now defaults to
> `true` (`group_vars/all.yml:268`), which adds `rabbit_quorum_queue = true` to the messaging config of a cloud that
> kept the 2023.1 default (e.g. `roles/nova-cell/templates/nova.conf.j2:207-216`;
> [F17](../reference/findings.md#f17)).

And independently of restarts, **every run pays the per-host work** [CODE]. Still holds in 2024.1: every full `deploy`
or `reconfigure` makes 10 `compare_container` calls per compute (common 3, iscsid with Cinder LVM, openvswitch 2,
neutron 1, nova-cell 3), each one a `kolla_set_configs --check` exec in the container once it exists and no compared
parameter differs (`roles/common/tasks/check-containers.yml:2-17`, `roles/nova-cell/tasks/check-containers.yml:2-22`,
`roles/openvswitch/tasks/check-containers.yml:2-18`, `roles/neutron/tasks/check-containers.yml:2-19`,
`roles/iscsi/tasks/check-containers.yml:2-18`; `module_utils/kolla_container_worker.py:20`, `:58-65`;
`module_utils/kolla_docker_worker.py:146-181`, Podman `module_utils/kolla_podman_worker.py:428-453`). The common
three run only when the `common` play runs (no tag or `-t common`, `site.yml:88-103`). The remote module invocations
of a no-change `-t nova` run, 27 per compute in 2024.1 (31 on the first compute), are counted from the task files in
[Compute scaling §2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files).
The number of task results per compute is [NOT AVAILABLE].

## Related

- [Compute scaling §5](../concepts/compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload) —
  the work multiplier and the restart multiplier
- [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify
- [Technical findings](../reference/findings.md) — [F6](../reference/findings.md#f6): global inputs are rendered into
  per-host files; [F16](../reference/findings.md#f16): the unit text is part of the container check
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Risk register](risk-register.md) — the risks, from [R1](risk-register.md#r1)
