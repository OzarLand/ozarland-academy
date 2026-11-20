---
title: Why a small change creates a large workload
description: Six small changes that become a large workload in Kolla-Ansible 2023.1, each with the reason and the source.
tags: [risk, scaling, loop-notify, nova, neutron, rabbitmq, images, reconfigure]
remember:
  - "One option for nova-compute is not small: it targets every compute, and loop-notify adds the libvirt and ssh restarts."
  - "A rebuilt image of one service restarts its sibling containers on the same host too."
  - "One extra controller changes the transport URL in every messaging service everywhere."
  - "Every run pays the per-host work: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute, independently of restarts. <span class=\"ev ev-code\">CODE</span>"
  - "Write config first, apply in controlled batches: <code>genconfig</code>, then <code>deploy-containers --limit</code> batch by batch."
scenarios:
  - title: "A one-line nova-compute change"
    situation: "Your cloud has 40 computes. A ticket asks you to change one option for nova-compute. Your colleague says: \"It's a one-line change, just run a full <code>reconfigure</code> now and close the ticket.\""
    ask: "What would you do?"
    choices:
      - text: "Write the config first with <code>genconfig</code>, then apply it with <code>deploy-containers --limit</code>, batch by batch."
        verdict: "best"
        why: "One option for nova-compute targets every compute, and loop-notify adds the libvirt and ssh restarts. The page points to the pattern \"Write config first, apply in controlled batches\": <code>genconfig</code>, then <code>deploy-containers --limit</code> batch by batch."
      - text: "Run a full <code>reconfigure</code> of the cloud right away, as suggested."
        verdict: "avoid"
        why: "The change is not small: one option for nova-compute targets every compute, and loop-notify adds the libvirt and ssh restarts. On top of that, every run pays the per-host work <span class=\"ev ev-code\">CODE</span>: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute."
      - text: "Run <code>reconfigure</code> on all computes in one go, but only at night."
        verdict: "risky"
        why: "The time of day does not change the size of the change: it still targets every compute, and loop-notify still adds the libvirt and ssh restarts on each of them. The page's pattern applies the config in controlled batches with <code>deploy-containers --limit</code>."
quiz:
  - q: "You change one option for nova-compute. Why is it a large change?"
    options: ["It is not: only one container restarts", "It targets every compute, and loop-notify adds the libvirt and ssh restarts"]
    answer: 1
    explain: "First row of the table."
  - q: "The image of one service is rebuilt. What else restarts?"
    options: ["Nothing else", "Its sibling containers on the same host"]
    answer: 1
    explain: "Row \"Rebuilt image of one service\"."
  - q: "Does a run with no change cost anything per compute?"
    options: ["No, nothing happens", "Yes: every full <code>deploy</code> or <code>reconfigure</code> makes 10 <code>compare_container</code> calls per compute"]
    answer: 1
    explain: "Every run pays the per-host work <span class=\"ev ev-code\">CODE</span>, independently of restarts."
---

# Why a small change creates a large workload

Why a small change can create a large workload: six small changes, each with why it is large and the source lines and
sections that show it. The per-host work that every run pays, independently of restarts, closes the page.

| Small change | Why it is large | Source |
|---|---|---|
| One option for nova-compute | targets every compute; loop-notify adds libvirt + ssh restarts | `nova.yml:117-135`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| `enable_<new service>: yes` | changes fluentd/logrotate on every host and `nova.conf` sections on every compute | `roles/common/defaults/main.yml:138-142`, `roles/common/tasks/config.yml:138-148`; [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code) |
| One extra controller | changes the transport URL in every messaging service everywhere | `group_vars/all.yml:212`; [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller) |
| A server-side ML2 option | no longer reaches the agents: `ml2_conf.ini` (and its overrides) is rendered for `neutron-server` and `neutron-infoblox-ipam-agent` only, and `openvswitch_agent.ini` no longer merges the `ml2_conf.ini` overrides (Ussuri did). A file added under `neutron/plugins/` in the custom config is still copied to every OVS and Linux bridge agent and restarts them | `roles/neutron/tasks/config.yml:158-178`, `:197-211`, `:15-21`, `:462-482`; [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code) |
| Rebuilt image of one service | its siblings on the same host restart too | `module_utils/kolla_docker_worker.py:116-131`; [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code); [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code) |
| Any OpenStack API service `-t <svc>` | runs the service's include in the `loadbalancer` play (haproxy configuration) and Keystone registration even with no change. It no longer runs common: Ussuri pulled common in through each role's `meta` dependency, 2023.1 roles have no `meta` and the common play is tagged `common` only; the DB sync runs on every `deploy` and, for most services, on every reconfigure. Neutron now too: its bootstrap (`neutron-db-manage ... upgrade head`) has no `kolla_action` condition any more and runs on every `deploy` and `reconfigure`. Infrastructure tags such as `-t haproxy` run the `loadbalancer` play with every service include, but no Keystone registration or DB sync | [Reconfigure Neutron §2](../operations/reconfigure-neutron.md#2-execution-and-targets), [Reconfigure a single service §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects); `site.yml:86-97`, `:99-342`; `roles/neutron/tasks/reconfigure.yml:2`, `roles/neutron/tasks/deploy.yml:20`, `roles/neutron/tasks/bootstrap_service.yml:2-21`; `kolla docker/neutron/neutron-server/extend_start.sh:5-13` |

And independently of restarts, **every run pays the per-host work** [CODE]. Every full `deploy` or `reconfigure` makes
10 `compare_container` calls per compute (common 3, iscsid with Cinder LVM, openvswitch 2, neutron 1, nova-cell 3;
Ussuri had 11 with chrony, a role that no longer exists), each one a `kolla_set_configs --check` exec once the
container exists (`roles/common/tasks/check-containers.yml:2-17`, `roles/nova-cell/tasks/check-containers.yml`,
`roles/openvswitch/tasks/check-containers.yml`, `roles/neutron/tasks/check-containers.yml`,
`roles/iscsi/tasks/check-containers.yml`; `module_utils/kolla_container_worker.py:20, :59-66`,
`module_utils/kolla_docker_worker.py:155-162`). The remote module invocations
of a no-change `-t nova` run are counted from the task files in [Compute scaling
§2](../concepts/compute-scaling-and-performance.md#2-work-per-compute-host-read-from-the-task-files). The number of task
results per compute is [NOT AVAILABLE].

## Related

- [Compute scaling §5](../concepts/compute-scaling-and-performance.md#5-why-a-small-change-becomes-a-large-workload) —
  the work multiplier and the restart multiplier
- [Tags §2.4](tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code) — loop-notify
- [Technical findings](../reference/findings.md) — [F6](../reference/findings.md#f6): global inputs are rendered into
  per-host files
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Risk register](risk-register.md) — the risks [R1–R25](risk-register.md#r1)
